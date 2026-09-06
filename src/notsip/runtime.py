from __future__ import annotations
import asyncio, hashlib, hmac, json, secrets
from pathlib import Path
from fastapi import Depends, FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from .config import settings
from .store import Store
from .policy import Policy, Risk
from .provider import Provider
from .tools import Registry, Tool, Workspace, Windows, calc, open_target
from .connectors import Web, Email, Calendar, OAuth, Browser
from .world import WorldModel
from .jobs import Scheduler
from .android_bridge import Pairing
from .agent import Agent
from .events import Event, EventBus
from .self_maintenance import SelfMaintenance

settings.ensure()
ROOT=Path(__file__).resolve().parents[2]
DATA=Path(settings.data_dir).resolve()
WS=Workspace(DATA/'workspace')
store=Store(DATA)
policy=Policy(settings.autonomy_level)
registry=Registry(); events=EventBus()
provider=Provider(settings.llm_base_url,settings.llm_api_key,settings.llm_model,settings.fallback_llm_base_url,settings.fallback_llm_api_key,settings.fallback_llm_model)
world=WorldModel(store); jobs=Scheduler(store); win=Windows(WS); web=Web(settings.brave_api_key); browser=Browser()
emailc=Email(settings.smtp_host,settings.smtp_port,settings.imap_host,settings.email_username,settings.email_password)
calendarc=Calendar(); oauth=OAuth(settings.oauth_authorize_url,settings.oauth_token_url,settings.oauth_client_id,settings.oauth_client_secret,settings.oauth_redirect_uri,settings.oauth_scopes)
pairing=Pairing(store); agent=Agent(settings,store,policy,registry,provider,world); maint=SelfMaintenance(ROOT)
auth_token=settings.api_key

def reg(name,desc,cap,risk,schema,fn,destructive=False): registry.add(Tool(name,desc,cap,risk,schema,fn,destructive))
reg('calculator','Safe arithmetic.','COMPUTE',Risk.LOW,{'type':'object','properties':{'expr':{'type':'string'}},'required':['expr']},calc)
reg('list_files','List authorized workspace files.','READ_FILES',Risk.LOW,{'type':'object','properties':{'query':{'type':'string'}}},lambda query='':{'status':'SUCCESS','files':WS.list(query)})
reg('read_file','Read an authorized text file.','READ_FILES',Risk.LOW,{'type':'object','properties':{'path':{'type':'string'}},'required':['path']},lambda path:{'status':'SUCCESS','content':WS.read(path)})
reg('write_file','Write an authorized workspace file.','WRITE_FILES',Risk.MEDIUM,{'type':'object','properties':{'path':{'type':'string'},'content':{'type':'string'}},'required':['path','content']},lambda path,content:{'status':'SUCCESS','path':WS.write(path,content)})
reg('windows_exec','Execute PowerShell on Windows.','CONTROL_COMPUTER',Risk.HIGH,{'type':'object','properties':{'command':{'type':'string'},'timeout':{'type':'integer'}},'required':['command']},win.exec,True)
reg('desktop_screenshot','Capture the Windows primary desktop.','CONTROL_COMPUTER',Risk.MEDIUM,{'type':'object','properties':{'filename':{'type':'string'}}},win.screenshot)
reg('open_target','Open a URL/file/application target.','CONTROL_COMPUTER',Risk.MEDIUM,{'type':'object','properties':{'target':{'type':'string'}},'required':['target']},open_target)
async def search_web(query,count=5):
    if not web.enabled:return {'status':'FAILURE','error':'web search not configured'}
    result=await web.search(query,max(1,min(count,20)))
    for x in result: store.fact(x.get('title',''),'brave',x.get('url',''),.6,{'description':x.get('description',''),'query':query})
    return {'status':'SUCCESS','results':result}
reg('web_search','Search live public web.','INTERNET_SEARCH',Risk.LOW,{'type':'object','properties':{'query':{'type':'string'},'count':{'type':'integer'}},'required':['query']},search_web)
reg('browser_extract','Extract visible text from a public web page.','INTERNET_SEARCH',Risk.MEDIUM,{'type':'object','properties':{'url':{'type':'string'}},'required':['url']},browser.extract)
reg('email_send','Send email via configured SMTP.','SEND_EMAIL',Risk.HIGH,{'type':'object','properties':{'to':{'type':'string'},'subject':{'type':'string'},'body':{'type':'string'}},'required':['to','subject','body']},emailc.send,True)
reg('email_search','Search configured mailbox.','READ_EMAIL',Risk.LOW,{'type':'object','properties':{'mailbox':{'type':'string'},'criteria':{'type':'string'},'limit':{'type':'integer'} }},emailc.search)
reg('calendar_parse','Parse a local ICS calendar.','READ_CALENDAR',Risk.LOW,{'type':'object','properties':{'path':{'type':'string'}},'required':['path']},lambda path:{'status':'SUCCESS','events':calendarc.parse(WS.path(path))})
reg('self_inspect','Inspect NOTSIP source inventory and hashes.','SELF_MAINTENANCE',Risk.LOW,{'type':'object','properties':{}},lambda:{'status':'SUCCESS','repository':str(ROOT),'files':maint.inventory()})
reg('self_read','Read a NOTSIP repository file.','SELF_MAINTENANCE',Risk.LOW,{'type':'object','properties':{'path':{'type':'string'}},'required':['path']},lambda path:{'status':'SUCCESS','path':path,'content':maint.read(path)})
reg('self_verify','Compile and test the NOTSIP repository.','SELF_MAINTENANCE',Risk.MEDIUM,{'type':'object','properties':{}},lambda:maint.verify())
reg('self_apply','Apply a verified Git patch through the controlled self-maintenance flow.','SELF_MAINTENANCE',Risk.HIGH,{'type':'object','properties':{'patch':{'type':'string'},'confirmation':{'type':'string'}},'required':['patch','confirmation']},lambda patch,confirmation:maint.apply_patch(patch,confirmation),True)

async def require_auth(request:Request):
    if auth_token and request.headers.get('authorization')!='Bearer '+auth_token: raise HTTPException(401,'Unauthorized')
class Message(BaseModel): message:str
class TaskIn(BaseModel): objective:str; handler:str='agent'; delay:float=0; interval:float|None=None; data:dict=Field(default_factory=dict); priority:int=0
class PairIn(BaseModel): code:str; device_id:str; name:str; platform:str; public_key:str=''
class QueueCommand(BaseModel): action:str; payload:dict=Field(default_factory=dict)
class ResultIn(BaseModel): command_id:str; status:str; result:dict=Field(default_factory=dict)
class SelfPatch(BaseModel): patch:str; confirmation:str
app=FastAPI(title='NOTSIP',version='0.8.0')

async def scheduled_agent(task):
    result=await agent.handle(task['objective'])
    store.audit('primary-user','scheduled task',task['objective'],'agent','execute',json.dumps(result,default=str))
    return result
jobs.register('agent',scheduled_agent)
jobs.register('self_verify',lambda task:asyncio.to_thread(maint.verify))

@app.on_event('startup')
async def startup(): app.state.worker=asyncio.create_task(jobs.loop())
@app.on_event('shutdown')
async def shutdown(): jobs.stop(); w=getattr(app.state,'worker',None); w and w.cancel()
@app.get('/')
async def root():
    ui=ROOT/'ui.html'
    return FileResponse(ui) if ui.exists() else JSONResponse({'name':'NOTSIP','version':'0.8.0','status':'online'})
@app.get('/api/health')
async def health(_:None=Depends(require_auth)): return {'status':'ok','identity':'NOTSIP','version':'0.8.0','llm':provider.enabled,'fallback_llm':provider.fallback_enabled,'memory':True,'world':True,'scheduler':True,'devices':len(store.devices())}
@app.get('/api/degraded')
async def degraded(_:None=Depends(require_auth)):
    reasons=[]
    if not provider.enabled and not provider.fallback_enabled: reasons.append('llm_provider_not_configured')
    if not web.enabled: reasons.append('web_search_not_configured')
    if not emailc.enabled: reasons.append('email_not_configured')
    if not oauth.configured: reasons.append('oauth_not_configured')
    return {'degraded':bool(reasons),'reasons':reasons}
@app.get('/api/status')
async def status(_:None=Depends(require_auth)): return {'identity':'NOTSIP','version':'0.8.0','autonomy_level':policy.level,'tools':[t.name for t in registry.all()],'devices':store.devices(),'world':world.snapshot(),'tasks':store.tasks(),'capabilities':{'llm':provider.enabled,'fallback_llm':provider.fallback_enabled,'web_search':web.enabled,'email':emailc.enabled,'oauth':oauth.configured,'browser':True,'windows':True,'android_pairing':True,'self_maintenance':True}}
@app.get('/api/memory')
async def memory(q:str='',limit:int=20,_:None=Depends(require_auth)): return {'memories':store.memories(agent.user,q,max(1,min(int(limit),100)))}
@app.get('/api/facts')
async def facts(limit:int=100,_:None=Depends(require_auth)): return {'facts':store.facts(max(1,min(int(limit),500)))}
@app.get('/api/world')
async def world_api(_:None=Depends(require_auth)): return world.snapshot()
@app.get('/api/audit')
async def audit(_:None=Depends(require_auth)): return {'audit':store.audit_recent()}
@app.get('/api/tasks')
async def tasks(_:None=Depends(require_auth)): return {'tasks':store.tasks()}
@app.post('/api/tasks')
async def create_task(body:TaskIn,_:None=Depends(require_auth)):
    if body.handler not in jobs.handlers: raise HTTPException(400,f'unknown task handler: {body.handler}')
    return {'task_id':jobs.create(body.objective,body.handler,body.delay,body.interval,body.data,body.priority),'handler':body.handler}
@app.post('/api/tasks/{task_id}/run')
async def run_task(task_id:str,_:None=Depends(require_auth)):
    if not store.row('SELECT id FROM tasks WHERE id=?',(task_id,)): raise HTTPException(404,'Task not found')
    store.task_update(task_id,state='PENDING',run_at=0); return {'status':'QUEUED','task_id':task_id}
@app.get('/api/devices')
async def devices(_:None=Depends(require_auth)): return {'devices':store.devices()}
@app.get('/api/devices/{device_id}/commands')
async def commands(device_id:str,token:str):
    if not store.device_token_valid(device_id,token): raise HTTPException(401,'Invalid device token')
    return {'commands':store.pull_commands(device_id)}
@app.post('/api/devices/{device_id}/commands')
async def queue_command(device_id:str,body:QueueCommand,_:None=Depends(require_auth)):
    if not store.row('SELECT id FROM devices WHERE id=?',(device_id,)): raise HTTPException(404,'Device not paired')
    d=policy.decide(Risk.MEDIUM)
    if not d.allowed:return {'status':'PARTIAL_SUCCESS','approval_required':d.needs_confirmation,'error':d.reason}
    return {'status':'SUCCESS','command_id':store.queue_command(device_id,body.action,body.payload)}
@app.post('/api/devices/result')
async def command_result(body:ResultIn):
    if not store.row('SELECT id FROM commands WHERE id=?',(body.command_id,)): raise HTTPException(404,'Command not found')
    store.command_result(body.command_id,body.status,body.result); return {'status':'SUCCESS'}
@app.get('/api/pair/code')
async def pair_code(_:None=Depends(require_auth)): return {'code':pairing.create_code()}
@app.post('/api/pair/consume')
async def pair_consume(body:PairIn):
    token=pairing.consume(body.code,body.device_id,body.name,body.platform,body.public_key)
    if not token: raise HTTPException(400,'Invalid or expired pairing code')
    return {'paired':True,'device_id':body.device_id,'token':token}
@app.post('/api/devices/heartbeat')
async def heartbeat(device_id:str,token:str):
    if not store.device_token_valid(device_id,token): raise HTTPException(401,'Invalid device token')
    store.heartbeat(device_id); return {'status':'SUCCESS','device_id':device_id}
@app.get('/api/search')
async def search(q:str,count:int=5,_:None=Depends(require_auth)):
    if not web.enabled: raise HTTPException(503,'Web search not configured')
    return {'results':await web.search(q,max(1,min(count,20)))}
@app.get('/api/email/status')
async def email_status(_:None=Depends(require_auth)): return {'configured':emailc.enabled,'smtp':bool(emailc.smtp_host),'imap':bool(emailc.imap_host),'username_configured':bool(emailc.username)}
@app.post('/api/email/send')
async def email_send(body:dict,_:None=Depends(require_auth)):
    d=policy.decide(Risk.HIGH)
    if not d.allowed:return {'status':'PARTIAL_SUCCESS','approval_required':d.needs_confirmation,'error':d.reason}
    return emailc.send(body['to'],body['subject'],body['body'])
@app.get('/api/email/search')
async def email_search(mailbox='INBOX',criteria='ALL',limit=20,_:None=Depends(require_auth)):
    if not emailc.imap_host: raise HTTPException(503,'IMAP not configured')
    return emailc.search(mailbox,criteria,max(1,min(int(limit),50)))
@app.get('/api/oauth/status')
async def oauth_status(_:None=Depends(require_auth)): return {'configured':oauth.configured,'authorize_url':bool(oauth.authorize),'token_url':bool(oauth.token),'client_id':bool(oauth.client_id),'redirect_uri':oauth.redirect}
@app.get('/api/oauth/authorize')
async def oauth_authorize(_:None=Depends(require_auth)):
    if not oauth.configured: raise HTTPException(503,'OAuth not configured')
    state=secrets.token_urlsafe(24); return {'state':state,'url':oauth.authorization_url(state)}
@app.get('/api/oauth/callback')
async def oauth_callback(code:str,state:str):
    result=await oauth.exchange(code); safe={k:('[redacted]' if any(s in k.lower() for s in ('token','secret')) else v) for k,v in result.items()}; return {'status':'SUCCESS','state':state,'response':safe}
@app.post('/api/events')
async def ingest_event(request:Request,x_notsip_signature:str|None=Header(default=None),_:None=Depends(require_auth)):
    raw=await request.body(); secret=settings.event_hmac_secret.encode()
    if secret:
        if not x_notsip_signature: raise HTTPException(401,'event signature required')
        expected=hmac.new(secret,raw,hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,x_notsip_signature): raise HTTPException(401,'invalid event signature')
    p=json.loads(raw); event=Event(p.get('type','external.event'),p.get('payload',{}),p.get('source','external')); await events.publish(event); return {'accepted':True,'event_type':event.type}
@app.get('/api/self/inspect')
async def self_inspect(_:None=Depends(require_auth)): return {'identity':'NOTSIP','repository':str(ROOT),'files':maint.inventory()}
@app.get('/api/self/verify')
async def self_verify(_:None=Depends(require_auth)): return maint.verify()
@app.get('/api/self/read')
async def self_read(path:str,_:None=Depends(require_auth)): return {'path':path,'content':maint.read(path)}
@app.post('/api/self/apply')
async def self_apply(body:SelfPatch,_:None=Depends(require_auth)):
    if not settings.self_modify_enabled:return {'status':'PARTIAL_SUCCESS','approval_required':True,'error':'self-modification is disabled by configuration'}
    d=policy.decide(Risk.HIGH)
    if not d.allowed:return {'status':'PARTIAL_SUCCESS','approval_required':True,'error':d.reason}
    result=maint.apply_patch(body.patch,body.confirmation); store.audit('primary-user','self-maintenance','apply patch','self_maintenance','execute',json.dumps(result,default=str)); return result
@app.websocket('/ws/events')
async def ws(sock:WebSocket):
    if auth_token and sock.headers.get('authorization')!='Bearer '+auth_token: await sock.close(code=4401); return
    await sock.accept(); q=events.subscribe()
    try:
        while True:
            event=await q.get(); await sock.send_json({'type':event.type,'payload':event.payload,'source':event.source,'timestamp':event.timestamp})
    except WebSocketDisconnect: pass
    finally: events.unsubscribe(q)
