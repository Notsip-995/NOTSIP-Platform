from __future__ import annotations
import ast, asyncio, dataclasses, json, operator, platform, secrets, sqlite3, subprocess, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

@dataclasses.dataclass
class Event:
    type: str
    payload: dict
    source: str = 'internal'
    timestamp: str = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class EventBus:
    def __init__(self): self.handlers={}; self.subscribers=[]
    def on(self, typ, fn): self.handlers.setdefault(typ, []).append(fn)
    async def publish(self, event):
        for fn in self.handlers.get(event.type, []):
            r=fn(event)
            if asyncio.iscoroutine(r): await r
        for q in list(self.subscribers): await q.put(event)
    def subscribe(self): q=asyncio.Queue(); self.subscribers.append(q); return q
    def unsubscribe(self,q):
        if q in self.subscribers: self.subscribers.remove(q)

class DB:
    def __init__(self,path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as c: c.executescript('''
        CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,role TEXT,content TEXT,ts REAL);
        CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY,user_id TEXT,kind TEXT,content TEXT,weight REAL,source TEXT,provenance TEXT,ts REAL);
        CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY,kind TEXT,name TEXT,data TEXT,updated REAL);
        CREATE TABLE IF NOT EXISTS relations(id INTEGER PRIMARY KEY,subject TEXT,predicate TEXT,object TEXT,confidence REAL,source TEXT,ts REAL);
        CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,objective TEXT,state TEXT,priority INTEGER,handler TEXT,data TEXT,created REAL,updated REAL,error TEXT);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,user_id TEXT,request TEXT,tool TEXT,action TEXT,result TEXT,ts REAL);
        CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY,name TEXT,platform TEXT,last_seen REAL,status TEXT,token_hash TEXT,public_key TEXT,data TEXT);
        CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY,device_id TEXT,action TEXT,payload TEXT,status TEXT,created REAL,updated REAL,result TEXT);
        CREATE TABLE IF NOT EXISTS pair_codes(code TEXT PRIMARY KEY,expires REAL);''')
    def q(self,sql,args=()):
        with sqlite3.connect(self.path) as c:
            c.row_factory=sqlite3.Row; return [dict(r) for r in c.execute(sql,args).fetchall()]
    def one(self,sql,args=()):
        rows=self.q(sql,args); return rows[0] if rows else None
    def ex(self,sql,args=()):
        with sqlite3.connect(self.path) as c: c.execute(sql,args)
    def remember(self,uid,kind,content,weight=.8,source='conversation',prov=None): self.ex('INSERT INTO memories(user_id,kind,content,weight,source,provenance,ts) VALUES(?,?,?,?,?,?,?)',(uid,kind,content,weight,source,json.dumps(prov or {}),time.time()))
    def memories(self,uid,q='',limit=20):
        return self.q('SELECT kind,content,weight,source,provenance,ts FROM memories WHERE user_id=? AND content LIKE ? ORDER BY weight DESC,ts DESC LIMIT ?',(uid,f'%{q}%',limit))
    def message(self,role,content): self.ex('INSERT INTO messages(role,content,ts) VALUES(?,?,?)',(role,content,time.time()))
    def history(self,n=30): return self.q('SELECT role,content FROM messages ORDER BY id DESC LIMIT ?',(n,))[::-1]
    def entity(self,eid,kind,name,data): self.ex('INSERT INTO entities(id,kind,name,data,updated) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET kind=excluded.kind,name=excluded.name,data=excluded.data,updated=excluded.updated',(eid,kind,name,json.dumps(data),time.time()))
    def entities(self): return self.q('SELECT * FROM entities ORDER BY updated DESC')
    def relation(self,s,p,o,confidence=.8,source='inference'): self.ex('INSERT INTO relations(subject,predicate,object,confidence,source,ts) VALUES(?,?,?,?,?,?)',(s,p,o,confidence,source,time.time()))
    def world(self): return {'entities':self.entities(),'relations':self.q('SELECT * FROM relations ORDER BY ts DESC')}
    def audit(self,uid,request,tool,action,result): self.ex('INSERT INTO audit(user_id,request,tool,action,result,ts) VALUES(?,?,?,?,?,?)',(uid,request,tool,action,result,time.time()))
    def pair_code(self):
        code=f'{secrets.randbelow(1_000_000):06d}'; self.ex('INSERT INTO pair_codes VALUES(?,?)',(code,time.time()+600)); return code
    def consume_pair(self,code):
        row=self.one('SELECT expires FROM pair_codes WHERE code=?',(code,)); ok=bool(row and row['expires']>=time.time())
        if ok: self.ex('DELETE FROM pair_codes WHERE code=?',(code,))
        return ok
    def pair_device(self,id,name,platform,public_key,token_hash): self.ex('INSERT INTO devices VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,platform=excluded.platform,last_seen=excluded.last_seen,status=excluded.status,token_hash=excluded.token_hash,public_key=excluded.public_key',(id,name,platform,time.time(),'ONLINE',token_hash,public_key,'{}'))
    def devices(self): return self.q('SELECT id,name,platform,last_seen,status,data FROM devices ORDER BY name')
    def queue_command(self,device_id,action,payload):
        cid=str(uuid.uuid4()); now=time.time(); self.ex('INSERT INTO commands VALUES(?,?,?,?,?,?,?,?)',(cid,device_id,action,json.dumps(payload),'PENDING',now,now,'')); return cid
    def pull_commands(self,device_id):
        rows=self.q("SELECT * FROM commands WHERE device_id=? AND status='PENDING' ORDER BY created LIMIT 20",(device_id,))
        for r in rows: self.ex("UPDATE commands SET status='DELIVERED',updated=? WHERE id=?",(time.time(),r['id'])); r['payload']=json.loads(r['payload'])
        return rows

class Policy:
    def __init__(self,level=2): self.level=int(level)
    def allow(self,risk,destructive=False):
        if risk<=0: return True,False,'allowed'
        if risk==1: return self.level>=2,self.level<3,'approval required' if self.level<3 else 'allowed'
        if risk==2 or destructive: return self.level>=4,True,'high-risk action requires autonomy 4'
        return False,True,'critical action blocked'

def safe_calc(expr):
    node=ast.parse(expr,mode='eval').body; ops={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.Pow:operator.pow,ast.Mod:operator.mod}
    def ev(n):
        if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)): return n.value
        if isinstance(n,ast.UnaryOp) and type(n.op) in (ast.UAdd,ast.USub): return (+1 if isinstance(n.op,ast.UAdd) else -1)*ev(n.operand)
        if isinstance(n,ast.BinOp) and type(n.op) in ops: return ops[type(n.op)](ev(n.left),ev(n.right))
        raise ValueError('unsupported expression')
    return ev(node)

class Workspace:
    def __init__(self,root): self.root=Path(root).resolve(); self.root.mkdir(parents=True,exist_ok=True)
    def path(self,rel):
        p=(self.root/rel).resolve()
        if self.root not in p.parents and p!=self.root: raise PermissionError('path outside NOTSIP workspace')
        return p
    def read(self,rel): return self.path(rel).read_text(encoding='utf-8')
    def write(self,rel,content): p=self.path(rel); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content,encoding='utf-8'); return str(p.relative_to(self.root))
    def list(self,q=''):
        return [str(p.relative_to(self.root)) for p in self.root.rglob('*') if p.is_file() and (not q or q.lower() in p.name.lower())][:500]

class WindowsNode:
    def __init__(self,workspace): self.workspace=workspace
    def exec(self,command,timeout=60):
        if platform.system()!='Windows': raise RuntimeError('Windows node required')
        r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-Command',command],cwd=str(self.workspace.root),capture_output=True,text=True,timeout=max(1,min(timeout,180)))
        return {'status':'SUCCESS' if r.returncode==0 else 'FAILURE','returncode':r.returncode,'stdout':r.stdout[-20000:],'stderr':r.stderr[-20000:]}
    def screenshot(self,filename='desktop.png'):
        if platform.system()!='Windows': raise RuntimeError('Windows node required')
        t=self.workspace.path(filename); target=str(t).replace("'","''")
        ps=f"Add-Type -AssemblyName System.Drawing;Add-Type -AssemblyName System.Windows.Forms;$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;$i=New-Object System.Drawing.Bitmap $b.Width,$b.Height;$g=[System.Drawing.Graphics]::FromImage($i);$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size);$i.Save('{target}',[System.Drawing.Imaging.ImageFormat]::Png);$g.Dispose();$i.Dispose()"
        r=self.exec(ps)
        if r['status']!='SUCCESS': raise RuntimeError(r['stderr'] or 'screenshot failed')
        return {'status':'SUCCESS','path':str(t.relative_to(self.workspace.root)),'size':t.stat().st_size}

class Browser:
    async def open_and_extract(self,url,wait=1000):
        try: from playwright.async_api import async_playwright
        except Exception as e: raise RuntimeError('Playwright is not installed') from e
        async with async_playwright() as p:
            browser=await p.chromium.launch(headless=True); page=await browser.new_page(); await page.goto(url,wait_until='domcontentloaded',timeout=30000); await page.wait_for_timeout(wait)
            result={'url':url,'title':await page.title(),'text':(await page.locator('body').inner_text())[:30000]}; await browser.close(); return result

class OpenAICompat:
    def __init__(self,base_url='',api_key='',model=''): self.base=(base_url or '').rstrip('/'); self.key=api_key or ''; self.model=model or ''
    @property
    def enabled(self): return bool(self.base and self.model)
    async def chat(self,messages,tools=None):
        import httpx
        headers={'Content-Type':'application/json'}
        if self.key: headers['Authorization']='Bearer '+self.key
        body={'model':self.model,'messages':messages,'temperature':0.2}
        if tools: body['tools']=tools
        async with httpx.AsyncClient(timeout=120) as c:
            r=await c.post(self.base+'/chat/completions',headers=headers,json=body); r.raise_for_status(); return r.json()

class Planner:
    def make_plan(self,objective):
        return {'objective':objective,'steps':[{'id':i+1,'description':s,'state':'PENDING'} for i,s in enumerate([f'Clarify success criteria for: {objective}','Gather required context and available resources','Execute the minimum safe actions','Observe and verify results','Record durable outcomes'])]}
