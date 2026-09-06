from __future__ import annotations
import asyncio,base64,hashlib,hmac,json,os,platform,secrets,sqlite3,subprocess,time,uuid,webbrowser
from pathlib import Path
from datetime import datetime
from email.message import EmailMessage
import smtplib,imaplib,email,httpx
from fastapi import FastAPI,Request,HTTPException,Depends,Header,WebSocket,WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel
from .config import settings

settings.ensure(); ROOT=Path(settings.data_dir).resolve(); WORK=ROOT/'workspace'; WORK.mkdir(parents=True,exist_ok=True); DB=ROOT/'runtime05.db'
app=FastAPI(title='NOTSIP',version='0.5.0'); UID='primary-user'

def conn(): c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
with conn() as c:c.executescript('''CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY,user_id TEXT,kind TEXT,content TEXT,weight REAL,ts REAL);CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,objective TEXT,state TEXT,priority INTEGER,data TEXT,created REAL,updated REAL,error TEXT);CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY,name TEXT,platform TEXT,last_seen REAL,status TEXT,token_hash TEXT,public_key TEXT,data TEXT);CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY,device_id TEXT,action TEXT,payload TEXT,status TEXT,created REAL,updated REAL,result TEXT);CREATE TABLE IF NOT EXISTS pairing(code TEXT PRIMARY KEY,expires REAL);CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,request TEXT,tool TEXT,action TEXT,result TEXT,ts REAL);''')

def auth(request:Request):
    k=os.getenv('NOTSIP_API_KEY','');
    if k and request.headers.get('Authorization')!='Bearer '+k: raise HTTPException(401,'Unauthorized')
    return True

def policy(risk):
    level=max(0,min(4,int(os.getenv('NOTSIP_AUTONOMY_LEVEL','2'))))
    if risk==0:return True
    if risk==1:return level>=2
    if risk==2:return level>=4
    return False

def remember(text,kind='semantic'):
    with conn() as c:c.execute('INSERT INTO memories(user_id,kind,content,weight,ts) VALUES(?,?,?,?,?)',(UID,kind,text,.9,time.time()))
def memories(q='',limit=20):
    like=f'%{q}%';
    with conn() as c:return [dict(r) for r in c.execute('SELECT kind,content,weight,ts FROM memories WHERE user_id=? AND content LIKE ? ORDER BY weight DESC,ts DESC LIMIT ?',(UID,like,limit)).fetchall()]
def audit(req,tool,action,res):
    with conn() as c:c.execute('INSERT INTO audit(request,tool,action,result,ts) VALUES(?,?,?,?,?)',(req,tool,action,res,time.time()))
def safe_path(p):
    target=(WORK/p).resolve();
    if WORK not in target.parents and target!=WORK: raise PermissionError('path outside NOTSIP workspace')
    return target

def calc(expr):
    import ast,operator
    node=ast.parse(expr,mode='eval').body; ops={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.Pow:operator.pow,ast.Mod:operator.mod}
    def ev(n):
        if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)):return n.value
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):return +ev(n.operand) if isinstance(n.op,ast.UAdd) else -ev(n.operand)
        if isinstance(n,ast.BinOp) and type(n.op) in ops:return ops[type(n.op)](ev(n.left),ev(n.right))
        raise ValueError('unsupported expression')
    return ev(node)

def ps(command,timeout=30):
    if platform.system()!='Windows': raise RuntimeError('Windows node required')
    p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-Command',command],cwd=WORK,capture_output=True,text=True,timeout=max(1,min(timeout,120)))
    return {'status':'SUCCESS' if p.returncode==0 else 'FAILURE','returncode':p.returncode,'stdout':p.stdout[-20000:],'stderr':p.stderr[-20000:]}

def screenshot(filename='desktop.png'):
    target=safe_path(filename)
    if platform.system()!='Windows': raise RuntimeError('Windows node required')
    path=str(target).replace("'","''')
    code="Add-Type -AssemblyName System.Drawing;Add-Type -AssemblyName System.Windows.Forms;$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;$i=New-Object System.Drawing.Bitmap $b.Width,$b.Height;$g=[System.Drawing.Graphics]::FromImage($i);$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size);$i.Save('"+path+"',[System.Drawing.Imaging.ImageFormat]::Png);$g.Dispose();$i.Dispose()"
    ps(code); return {'status':'SUCCESS','path':str(target.relative_to(WORK)),'size':target.stat().st_size}

def list_files(q=''):
    return [str(p.relative_to(WORK)) for p in WORK.rglob('*') if p.is_file() and (not q or q.lower() in p.name.lower())][:500]

async def web_search(q,count=5):
    key=os.getenv('NOTSIP_BRAVE_API_KEY','')
    if not key: raise RuntimeError('Brave Search not configured')
    async with httpx.AsyncClient(timeout=20) as c:
        r=await c.get('https://api.search.brave.com/res/v1/web/search',params={'q':q,'count':count},headers={'Accept':'application/json','X-Subscription-Token':key}); r.raise_for_status(); d=r.json()
    return [{'title':x.get('title'),'url':x.get('url'),'description':x.get('description')} for x in d.get('web',{}).get('results',[])]

async def llm(messages,tools):
    base=os.getenv('NOTSIP_LLM_BASE_URL','').rstrip('/'); model=os.getenv('NOTSIP_LLM_MODEL',''); key=os.getenv('NOTSIP_LLM_API_KEY','')
    if not base or not model: raise RuntimeError('LLM provider not configured')
    h={'Content-Type':'application/json'};
    if key:h['Authorization']='Bearer '+key
    async with httpx.AsyncClient(timeout=120) as c:
        r=await c.post(base+'/chat/completions',headers=h,json={'model':model,'messages':messages,'tools':tools,'temperature':.2});r.raise_for_status();return r.json()

TOOL_DEFS=[
 {'name':'calculator','description':'Calculate safe arithmetic','risk':0,'schema':{'type':'object','properties':{'expr':{'type':'string'}},'required':['expr']}},
 {'name':'list_files','description':'List files in the NOTSIP workspace','risk':0,'schema':{'type':'object','properties':{'query':{'type':'string'}}}},
 {'name':'read_file','description':'Read a workspace text file','risk':0,'schema':{'type':'object','properties':{'path':{'type':'string'}},'required':['path']}},
 {'name':'open_target','description':'Open a URL on the Windows desktop','risk':1,'schema':{'type':'object','properties':{'target':{'type':'string'}},'required':['target']}},
 {'name':'desktop_screenshot','description':'Capture the Windows primary desktop','risk':1,'schema':{'type':'object','properties':{'filename':{'type':'string'}}}},
 {'name':'windows_exec','description':'Run PowerShell on the Windows node','risk':2,'schema':{'type':'object','properties':{'command':{'type':'string'},'timeout':{'type':'integer'}},'required':['command']}},
 {'name':'web_search','description':'Search the live public web','risk':0,'schema':{'type':'object','properties':{'query':{'type':'string'},'count':{'type':'integer'}},'required':['query']}},
]
SCHEMAS=[{'type':'function','function':{'name':t['name'],'description':t['description'],'parameters':t['schema']}} for t in TOOL_DEFS]
async def tool(name,args):
    spec=next((x for x in TOOL_DEFS if x['name']==name),None)
    if not spec:return {'status':'FAILURE','error':'unknown tool'}
    if not policy(spec['risk']):return {'status':'PARTIAL_SUCCESS','approval_required':True,'error':'blocked by autonomy policy'}
    try:
        if name=='calculator':r=calc(args['expr'])
        elif name=='list_files':r=list_files(args.get('query',''))
        elif name=='read_file':r=safe_path(args['path']).read_text(encoding='utf-8')
        elif name=='open_target':r={'opened':webbrowser.open(args['target']),'target':args['target']}
        elif name=='desktop_screenshot':r=screenshot(args.get('filename','desktop.png'))
        elif name=='windows_exec':r=ps(args['command'],args.get('timeout',30))
        else:r=await web_search(args['query'],args.get('count',5))
        audit(name,name,'execute',json.dumps(r,default=str));return r if isinstance(r,dict) else {'status':'SUCCESS','result':r}
    except Exception as e:return {'status':'FAILURE','error':str(e)}

class Msg(BaseModel):message:str
class Pair(BaseModel):code:str;device_id:str;name:str;platform:str;public_key:str=''
class Beat(BaseModel):device_id:str;token:str;state:dict={}
class Cmd(BaseModel):device_id:str;token:str;command_id:str;status:str;result:dict={}
class Task(BaseModel):objective:str;priority:int=0;data:dict={}

def device_ok(device,token):
    with conn() as c:r=c.execute('SELECT token_hash FROM devices WHERE id=?',(device,)).fetchone()
    return bool(r and secrets.compare_digest(r['token_hash'],hashlib.sha256(token.encode()).hexdigest()))

@app.get('/')
async def root(): return FileResponse(Path(__file__).resolve().parents[1]/'ui.html')
@app.get('/api/health')
async def health(_:bool=Depends(auth)):return {'status':'ok','identity':'NOTSIP','version':'0.5.0','llm':bool(os.getenv('NOTSIP_LLM_BASE_URL') and os.getenv('NOTSIP_LLM_MODEL')),'web_search':bool(os.getenv('NOTSIP_BRAVE_API_KEY')),'devices':len(memories('device',99))}
@app.get('/api/status')
async def status(_:bool=Depends(auth)):
    with conn() as c: ds=[dict(r) for r in c.execute('SELECT id,name,platform,last_seen,status FROM devices ORDER BY name')];ts=[dict(r) for r in c.execute('SELECT * FROM tasks ORDER BY priority DESC,created ASC').fetchall()]
    return {'identity':'NOTSIP','version':'0.5.0','tools':[t['name'] for t in TOOL_DEFS],'autonomy_level':int(os.getenv('NOTSIP_AUTONOMY_LEVEL','2')),'devices':ds,'tasks':ts,'workspace':str(WORK)}
@app.post('/api/message')
async def message(body:Msg,_:bool=Depends(auth)):
    text=body.message.strip(); DBX=conn(); DBX.execute('INSERT INTO memories(user_id,kind,content,weight,ts) VALUES(?,?,?,?,?)',(UID,'episodic','USER: '+text,.2,time.time())); DBX.commit(); DBX.close()
    import re
    m=re.match(r'^remember(?: that)?\s+(.+)$',text,re.I)
    if m: remember(m.group(1)); return {'response':"I'll remember that: "+m.group(1),'status':'SUCCESS'}
    if ('what do you remember' in text.lower() or 'what do you know about me' in text.lower()):
        return {'response':'I remember:\n'+'\n'.join('- '+x['content'] for x in memories('',20)),'status':'SUCCESS'}
    try:
        ctx={'time':datetime.now().astimezone().isoformat(),'memory':memories(text,12),'world':{},'devices':[]}
        msgs=[{'role':'system','content':'You are NOTSIP, a persistent AI operating layer. Never invent access or success. Use real tools when appropriate. Context='+json.dumps(ctx,default=str)},{'role':'user','content':text}]
        for _ in range(int(os.getenv('NOTSIP_MAX_TOOL_ROUNDS','8'))):
            data=await llm(msgs,SCHEMAS); msg=data['choices'][0]['message']; msgs.append(msg);calls=msg.get('tool_calls') or []
            if not calls:
                return {'response':msg.get('content',''),'status':'SUCCESS'}
            for call in calls:
                n=call['function']['name'];a=json.loads(call['function'].get('arguments') or '{}');res=await tool(n,a);msgs.append({'role':'tool','tool_call_id':call['id'],'name':n,'content':json.dumps(res,default=str)})
    except Exception as e:return {'response':f'NOTSIP degraded: {e}','status':'DEGRADED'}
    return {'response':'Agent loop stopped safely.','status':'UNKNOWN'}
@app.get('/api/memory')
async def memory(q:str='',limit:int=20,_:bool=Depends(auth)):return {'memories':memories(q,max(1,min(limit,100)))}
@app.get('/api/audit')
async def audit_api(_:bool=Depends(auth)):
    with conn() as c:return {'audit':[dict(r) for r in c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 200').fetchall()]}
@app.post('/api/tasks')
async def tasks_create(body:Task,_:bool=Depends(auth)):
    tid=str(uuid.uuid4());now=time.time();
    with conn() as c:c.execute('INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?)',(tid,body.objective,'PENDING',body.priority,json.dumps(body.data),now,now,''))
    return {'task_id':tid}
@app.get('/api/tasks')
async def tasks_api(_:bool=Depends(auth)):
    with conn() as c:return {'tasks':[dict(r) for r in c.execute('SELECT * FROM tasks ORDER BY priority DESC,created ASC').fetchall()]}
@app.get('/api/search')
async def search(q:str,_:bool=Depends(auth)):return {'results':await brave(q)}
@app.get('/api/pair/code')
async def pair_code(_:bool=Depends(auth)):
    code=f'{secrets.randbelow(1000000):06d}';
    with conn() as c:c.execute('INSERT OR REPLACE INTO pairing VALUES(?,?)',(code,time.time()+600))
    return {'code':code,'expires_in':600}
@app.post('/api/pair/consume')
async def pair_consume(body:Pair):
    with conn() as c:r=c.execute('SELECT expires FROM pairing WHERE code=?',(body.code,)).fetchone()
    if not r or r['expires']<time.time():raise HTTPException(400,'invalid or expired pairing code')
    token=secrets.token_urlsafe(32); h=hashlib.sha256(token.encode()).hexdigest()
    with conn() as c:c.execute('DELETE FROM pairing WHERE code=?',(body.code,));c.execute('INSERT INTO devices VALUES(?,?,?,?,?,?,?,?)',(body.device_id,body.name,body.platform,time.time(),'ONLINE',h,body.public_key,'{}'))
    return {'paired':True,'device_id':body.device_id,'token':token}
@app.post('/api/devices/heartbeat')
async def heartbeat(body:Beat):
    if not device_ok(body.device_id,body.token):raise HTTPException(401,'invalid device token')
    with conn() as c:c.execute('UPDATE devices SET last_seen=?,status=?,data=? WHERE id=?',(time.time(),'ONLINE',json.dumps(body.state),body.device_id))
    return {'status':'SUCCESS'}
@app.get('/api/devices/commands')
async def device_commands(device_id:str,token:str):
    if not device_ok(device_id,token):raise HTTPException(401,'invalid device token')
    with conn() as c:rows=c.execute("SELECT * FROM commands WHERE device_id=? AND status='PENDING' ORDER BY created LIMIT 20",(device_id,)).fetchall();
    with conn() as c:
        for r in rows:c.execute("UPDATE commands SET status='DELIVERED',updated=? WHERE id=?",(time.time(),r['id']))
    return {'commands':[dict(r, payload=json.loads(r['payload'])) for r in rows]}
@app.post('/api/devices/command-result')
async def device_result(body:Cmd):
    if not device_ok(body.device_id,body.token):raise HTTPException(401,'invalid device token')
    with conn() as c:c.execute('UPDATE commands SET status=?,result=?,updated=? WHERE id=?',(body.status,json.dumps(body.result),time.time(),body.command_id))
    return {'status':'SUCCESS'}
@app.post('/api/devices/{device_id}/commands')
async def enqueue(device_id:str,body:dict,_:bool=Depends(auth)):
    with conn() as c:r=c.execute('SELECT id FROM devices WHERE id=?',(device_id,)).fetchone()
    if not r:raise HTTPException(404,'device not paired')
    cid=str(uuid.uuid4());now=time.time()
    with conn() as c:c.execute('INSERT INTO commands VALUES(?,?,?,?,?,?,?,?)',(cid,device_id,body.get('action',''),json.dumps(body.get('payload',{})),'PENDING',now,now,''))
    return {'command_id':cid}
@app.post('/api/events')
async def event_ingest(request:Request,x_notsip_signature:str|None=Header(None),_:bool=Depends(auth)):
    raw=await request.body(); secret=os.getenv('NOTSIP_EVENT_HMAC_SECRET','')
    if secret:
        exp=hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()
        if not x_notsip_signature or not hmac.compare_digest(exp,x_notsip_signature):raise HTTPException(401,'invalid event signature')
    p=json.loads(raw); return {'accepted':True,'event_id':str(uuid.uuid4()),'type':p.get('type')}
@app.websocket('/ws/events')
async def ws(sock:WebSocket):
    await sock.accept()
    try:
        while True: await sock.send_json({'type':'heartbeat','timestamp':time.time()}); await asyncio.sleep(10)
    except WebSocketDisconnect: pass
