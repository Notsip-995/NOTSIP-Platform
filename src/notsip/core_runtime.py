from __future__ import annotations
import asyncio, hashlib, hmac, json, secrets
from datetime import datetime, timezone
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from .config import settings
from .store import Store
from .policy import Policy, Risk
from .provider import Provider
from .tools import Registry, Tool, calc, Workspace, Windows, open_target
from .connectors import Web, Email, Calendar, OAuth, Browser
from .world import WorldModel
from .jobs import Scheduler
from .android_bridge import Pairing
from .agent import Agent
from .events import Event, EventBus
from .self_maintenance import SelfMaintenance

settings.ensure()
ROOT = Path(__file__).resolve().parents[2]
DATA = Path(settings.data_dir).resolve()
WS = Workspace(DATA / 'workspace')
store = Store(DATA)
policy = Policy(settings.autonomy_level)
registry = Registry()
events = EventBus()
provider = Provider(settings.llm_base_url, settings.llm_api_key, settings.llm_model)
world = WorldModel(store)
jobs = Scheduler(store)
win = Windows(WS)
web = Web(settings.brave_api_key)
browser = Browser()
emailc = Email(settings.smtp_host, settings.smtp_port, settings.imap_host, settings.email_username, settings.email_password)
calendarc = Calendar()
oauth = OAuth(settings.oauth_authorize_url, settings.oauth_token_url, settings.oauth_client_id, settings.oauth_client_secret, settings.oauth_redirect_uri, settings.oauth_scopes)
pairing = Pairing(store)
agent = Agent(settings, store, policy, registry, provider, world)
maint = SelfMaintenance(ROOT)


def reg(name, desc, capability, risk, schema, fn, destructive=False):
    registry.add(Tool(name, desc, capability, risk, schema, fn, destructive))

reg('calculator', 'Safe arithmetic.', 'COMPUTE', Risk.LOW, {'type':'object','properties':{'expr':{'type':'string'}},'required':['expr']}, calc)
reg('list_files', 'List files in the NOTSIP workspace.', 'READ_FILES', Risk.LOW, {'type':'object','properties':{'query':{'type':'string'}}}, lambda query='': {'status':'SUCCESS','files':WS.list(query)})
reg('read_file', 'Read a text file in the workspace.', 'READ_FILES', Risk.LOW, {'type':'object','properties':{'path':{'type':'string'}},'required':['path']}, lambda path: {'status':'SUCCESS','content':WS.read(path)})
reg('write_file', 'Write a text file in the workspace.', 'WRITE_FILES', Risk.MEDIUM, {'type':'object','properties':{'path':{'type':'string'},'content':{'type':'string'}},'required':['path','content']}, lambda path,content: {'status':'SUCCESS','path':WS.write(path,content)})
reg('windows_exec', 'Execute PowerShell on the Windows node.', 'CONTROL_COMPUTER', Risk.HIGH, {'type':'object','properties':{'command':{'type':'string'},'timeout':{'type':'integer','minimum':1,'maximum':180}},'required':['command']}, win.exec, True)
reg('desktop_screenshot', 'Capture the primary Windows desktop.', 'CONTROL_COMPUTER', Risk.MEDIUM, {'type':'object','properties':{'filename':{'type':'string'}}}, win.screenshot)
reg('open_target', 'Open a URL, file, or application target using Windows.', 'CONTROL_COMPUTER', Risk.MEDIUM, {'type':'object','properties':{'target':{'type':'string'}},'required':['target']}, open_target)

async def websearch(query, count=5):
    if not web.enabled: return {'status':'FAILURE','error':'web search not configured'}
    results = await web.search(query, max(1, min(count, 20)))
    for item in results:
        store.fact(item.get('title',''), 'brave', item.get('url',''), .6, {'description':item.get('description',''), 'query':query})
    return {'status':'SUCCESS','results':results}
reg('web_search', 'Search the live public web.', 'INTERNET_SEARCH', Risk.LOW, {'type':'object','properties':{'query':{'type':'string'},'count':{'type':'integer'}},'required':['query']}, websearch)
reg('browser_extract', 'Open a public page with Playwright and extract visible text.', 'INTERNET_SEARCH', Risk.MEDIUM, {'type':'object','properties':{'url':{'type':'string'}},'required':['url']}, browser.extract)
reg('email_send', 'Send an email via configured SMTP.', 'SEND_EMAIL', Risk.HIGH, {'type':'object','properties':{'to':{'type':'string'},'subject':{'type':'string'},'body':{'type':'string'}},'required':['to','subject','body']}, emailc.send, True)
reg('email_search', 'Search the configured mailbox.', 'READ_EMAIL', Risk.LOW, {'type':'object','properties':{'mailbox':{'type':'string'},'criteria':{'type':'string'},'limit':{'type':'integer'}}}, emailc.search)
reg('calendar_parse', 'Parse an ICS calendar file.', 'READ_CALENDAR', Risk.LOW, {'type':'object','properties':{'path':{'type':'string'}},'required':['path']}, lambda path: {'status':'SUCCESS','events':calendarc.parse(WS.path(path))})

auth_token = settings.api_key
async def require_auth(request: Request):
    if auth_token and request.headers.get('authorization') != 'Bearer ' + auth_token:
        raise HTTPException(401, 'Unauthorized')

class Message(BaseModel): message: str
class TaskIn(BaseModel):
    objective: str
    handler: str = 'agent'
    delay: float = 0
    interval: float | None = None
    data: dict = Field(default_factory=dict)
    priority: int = 0
class PairIn(BaseModel):
    code: str; device_id: str; name: str; platform: str; public_key: str = ''
class ResultIn(BaseModel): command_id: str; status: str; result: dict = Field(default_factory=dict)
class QueueCommand(BaseModel): action: str; payload: dict = Field(default_factory=dict)
class SelfPatch(BaseModel): patch: str; confirmation: str

app = FastAPI(title='NOTSIP', version='0.8.0')

async def scheduled_agent(task):
    result = await agent.handle(task['objective'])
    store.audit('primary-user', 'scheduled task', task['objective'], 'agent', 'execute', json.dumps(result, default=str))
    return result
jobs.register('agent', scheduled_agent)
jobs.register('self_verify', lambda task: asyncio.to_thread(maint.verify))

@app.on_event('startup')
async def startup(): app.state.worker = asyncio.create_task(jobs.loop())
@app.on_event('shutdown')
async def shutdown():
    jobs.stop(); worker = getattr(app.state, 'worker', None)
    if worker: worker.cancel()

@app.get('/')
async def root():
    ui = ROOT / 'ui.html'
    return FileResponse(ui) if ui.exists() else JSONResponse({'name':'NOTSIP','version':'0.8.0','status':'online'})

@app.get('/api/health')
async def health(_: None = Depends(require_auth)):
    return {'status':'ok','identity':'NOTSIP','version':'0.8.0','llm':provider.enabled,'memory':True,'world':True,'scheduler':True,'devices':len(store.devices())}

@app.get('/api/degraded')
async def degraded(_: None = Depends(require_auth)):
    reasons=[]
    if not provider.enabled: reasons.append('llm_provider_not_configured')
    if not web.enabled: reasons.append('web_search_not_configured')
    if not emailc.enabled: reasons.append('email_not_configured')
    if not oauth.configured: reasons.append('oauth_not_configured')
    return {'degraded':bool(reasons),'reasons':reasons}

@app.get('/api/status')
async def status(_: None = Depends(require_auth)):
    return {'identity':'NOTSIP','version':'0.8.0','autonomy_level':policy.level,'tools':[t.name for t in registry.all()],'devices':store.devices(),'world':world.snapshot(),'tasks':store.tasks(),'capabilities':{'llm':provider.enabled,'web_search':web.enabled,'email':emailc.enabled,'oauth':oauth.configured,'browser':True,'windows':True,'android_pairing':True,'self_maintenance':True}}

@app.get('/api/memory')
async def memory(q:str='',limit:int=20,_: None = Depends(require_auth)):
    return {'memories':store.memories(agent.user,q,max(1,min(int(limit),100)))}
@app.get('/api/facts')
async def facts(limit:int=100,_: None = Depends(require_auth)):
    return {'facts':store.facts(max(1,min(int(limit),500)))}
@app.get('/api/world')
async def world_state(_: None = Depends(require_auth)): return world.snapshot()
@app.get('/api/audit')
async def audit(_: None = Depends(require_auth)): return {'audit':store.audit_recent()}

@app.get('/api/tasks')
async def tasks(_: None = Depends(require_auth)): return {'tasks':store.tasks()}
@app.post('/api/tasks')
async def create_task(body:TaskIn,_: None = Depends(require_auth)):
    handler=body.handler or 'agent'
    if handler not in jobs.handlers: raise HTTPException(400,f'unknown task handler: {handler}')
    return {'task_id':jobs.create(body.objective,handler,body.delay,body.interval,body.data,body.priority),'handler':handler}
@app.post('/api/tasks/{task_id}/run')
async def run_task(task_id:str,_: None = Depends(require_auth)):
    task=store.row('SELECT * FROM tasks WHERE id=?',(task_id,))
    if not task: raise HTTPException(404,'Task not found')
    store.task_update(task_id,state='PENDING',run_at=0)
    return {'status':'QUEUED','task_id':task_id}

@app.get('/api/devices')
async def devices(_: None = Depends(require_auth)): return {'devices':store.devices()}
@app.get('/api/devices/{device_id}/commands')
async def device_commands(device_id:str,token:str):
    if not store.device_token_valid(device_id,token): raise HTTPException(401,'Invalid device token')
    return {'commands':store.pull_commands(device_id)}
@app.post('/api/devices/{device_id}/commands')
async def queue_device_command(device_id:str,body:QueueCommand,_: None = Depends(require_auth)):
    if not store.row('SELECT id FROM devices WHERE id=?',(device_id,)): raise HTTPException(404,'Device not paired')
    d=policy.decide(Risk.MEDIUM)
    if not d.allowed: return {'status':'PARTIAL_SUCCESS','approval_required':d.needs_confirmation,'error':d.reason}
    return {'status':'SUCCESS','command_id':store.queue_command(device_id,body.action,body.payload)}
@app.post('/api/devices/result')
async def device_result(body:ResultIn):
    if not store.row('SELECT id FROM commands WHERE id=?',(body.command_id,)): raise HTTPException(404,'Command not found')
    store.command_result(body.command_id,body.status,body.result); return {'status':'SUCCESS'}

@app.get('/api/pair/code')
async def pair_code(_: None = Depends(require_auth)): return {'code':pairing.create_code()}
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
async def search(q:str,count:int=5,_: None = Depends(require_auth)):
    if not web.enabled: raise HTTPException(503,'Web search not configured')
    return {'results':await web.search(q,max(1,min(count,20)))}
@app.get('/api/email/status')
async def email_status(_: None = Depends(require_auth)):
    return {'configured':emailc.enabled,'smtp':bool(emailc.smtp_host),'imap':bool(emailc.imap_host),'username_configured':bool(emailc.username)}
@app.post('/api/email/send')
async def email_send(body:dict,_: None = Depends(require_auth)):
    d=policy.decide(Risk.HIGH)
    if not d.allowed: return {'status':'PARTIAL_SUCCESS','approval_required':d.needs_confirmation,'error':d.reason}
    return emailc.send(body['to'],body['subject'],body['body'])
@app.get('/api/email/search')
async def email_search(mailbox:str='INBOX',criteria:str='ALL',limit:int=20,_: None = Depends(require_auth)):
    if not emailc.imap_host: raise HTTPException(503,'IMAP not configured')
    return emailc.search(mailbox,criteria,max(1,min(limit,50)))
@app.get('/api/oauth/status')
async def oauth_status(_: None = Depends(require_auth)):
    return {'configured':oauth.configured,'authorize_url':bool(oauth.authorize),'token_url':bool(oauth.token),'client_id':bool(oauth.client_id),'redirect_uri':oauth.redirect}
@app.get('/api/oauth/authorize')
async def oauth_authorize(_: None = Depends(require_auth)):
    if not oauth.configured: raise HTTPException(503,'OAuth is not configured')
    state=secrets.token_urlsafe(24); return {'state':state,'url':oauth.authorization_url(state)}
@app.get('/api/oauth/callback')
async def oauth_callback(code:str,state:str):
    result=await oauth.exchange(code)
    safe={k:('[redacted]' if any(x in k.lower() for x in ('token','secret')) else v) for k,v in result.items()}
    return {'status':'SUCCESS','state':state,'response':safe}

@app.post('/api/events')
async def ingest_event(request:Request,x_notsip_signature:str|None=Header(default=None),_: None = Depends(require_auth)):
    raw=await request.body(); secret=settings.event_hmac_secret.encode()
    if secret:
        if not x_notsip_signature: raise HTTPException(401,'event signature required')
        expected=hmac.new(secret,raw,hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,x_notsip_signature): raise HTTPException(401,'invalid event signature')
    p=json.loads(raw); event=Event(p.get('type','external.event'),p.get('payload',{}),p.get('source','external'))
    await events.publish(event); return {'accepted':True,'event_type':event.type}

@app.get('/api/self/inspect')
async def self_inspect(_: None = Depends(require_auth)): return {'identity':'NOTSIP','repository':str(ROOT),'files':maint.inventory()}
@app.get('/api/self/verify')
async def self_verify(_: None = Depends(require_auth)): return maint.verify()
@app.get('/api/self/read')
async def self_read(path:str,_: None = Depends(require_auth)): return {'path':path,'content':maint.read(path)}
@app.post('/api/self/apply')
async def self_apply(body:SelfPatch,_: None = Depends(require_auth)):
    if not policy.decide(Risk.HIGH).allowed or settings.self_modify_enabled is False:
        return {'status':'PARTIAL_SUCCESS','approval_required':True,'error':'self-modification is disabled by policy/config'}
    result=maint.apply_patch(body.patch,body.confirmation)
    store.audit('primary-user','self-maintenance','apply patch','self_maintenance','execute',json.dumps(result,default=str))
    return result

@app.websocket('/ws/events')
async def ws(sock:WebSocket):
    if auth_token and sock.headers.get('authorization')!='Bearer '+auth_token:
        await sock.close(code=4401); return
    await sock.accept(); q=events.subscribe()
    try:
        while True:
            event=await q.get(); await sock.send_json({'type':event.type,'payload':event.payload,'source':event.source,'timestamp':event.timestamp})
    except WebSocketDisconnect: pass
    finally: events.unsubscribe(q)
