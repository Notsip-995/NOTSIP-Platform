from __future__ import annotations
import asyncio, base64, hashlib, hmac, json, secrets, time
from pathlib import Path
from urllib.parse import quote
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field
from .config import settings
from .store import Store
from .policy import Policy, Risk
from .provider import Provider
from .tools import Registry, Tool, Workspace, Windows, calc, open_target
from .connectors import Web, Email, Calendar, Browser
from .world import WorldModel
from .jobs import Scheduler
from .android_bridge import Pairing
from .agent import Agent
from .events import Event, EventBus
from .self_maintenance import SelfMaintenance
from .windows_automation import WindowsAutomation
from .media import MediaEngine
from .nodes import NodeRegistry, RecoveryManager
from .intelligence import Intelligence
from .security import AuthManager, pkce_pair

settings.ensure(); ROOT=Path(__file__).resolve().parents[2]; DATA=Path(settings.data_dir).resolve(); WS=Workspace(DATA/'workspace')
store=Store(DATA); policy=Policy(settings.autonomy_level); registry=Registry(); events=EventBus()
provider=Provider(settings.llm_base_url,settings.llm_api_key,settings.llm_model,settings.fallback_llm_base_url,settings.fallback_llm_api_key,settings.fallback_llm_model)
world=WorldModel(store); jobs=Scheduler(store); win=Windows(WS); ui=WindowsAutomation(); web=Web(settings.brave_api_key); browser=Browser()
emailc=Email(settings.smtp_host,settings.smtp_port,settings.imap_host,settings.email_username,settings.email_password)
calendarc=Calendar(); pairing=Pairing(store); agent=Agent(settings,store,policy,registry,provider,world); maint=SelfMaintenance(ROOT)
media=MediaEngine(settings,provider,DATA); nodes=NodeRegistry(store,settings.node_shared_secret); recovery=RecoveryManager(DATA); intellect=Intelligence(store,world); auth=AuthManager(settings,ROOT)

def reg(name,desc,cap,risk,schema,fn,destructive=False): registry.add(Tool(name,desc,cap,risk,schema,fn,destructive))
reg('calculator','Safe arithmetic.','COMPUTE',Risk.LOW,{'type':'object','properties':{'expr':{'type':'string'}},'required':['expr']},calc)
reg('list_files','List authorized workspace files.','READ_FILES',Risk.LOW,{'type':'object','properties':{'query':{'type':'string'}}},lambda query='':{'status':'SUCCESS','files':WS.list(query)})
reg('read_file','Read authorized workspace text.','READ_FILES',Risk.LOW,{'type':'object','properties':{'path':{'type':'string'}},'required':['path']},lambda path:{'status':'SUCCESS','content':WS.read(path)})
reg('write_file','Write authorized workspace text.','WRITE_FILES',Risk.MEDIUM,{'type':'object','properties':{'path':{'type':'string'},'content':{'type':'string'}},'required':['path','content']},lambda path,content:{'status':'SUCCESS','path':WS.write(path,content)})
reg('windows_exec','Execute PowerShell on the Windows node.','CONTROL_COMPUTER',Risk.HIGH,{'type':'object','properties':{'command':{'type':'string'},'timeout':{'type':'integer','minimum':1,'maximum':180}},'required':['command']},win.exec,True)
reg('desktop_screenshot','Capture the Windows primary desktop.','CONTROL_COMPUTER',Risk.MEDIUM,{'type':'object','properties':{'filename':{'type':'string'}}},win.screenshot)
reg('open_target','Open a Windows URL, file, or application target.','CONTROL_COMPUTER',Risk.MEDIUM,{'type':'object','properties':{'target':{'type':'string'}},'required':['target']},open_target)
reg('windows_list','List visible Windows desktop windows.','CONTROL_COMPUTER',Risk.MEDIUM,{'type':'object','properties':{'title_re':{'type':'string'}}},ui.windows)
reg('windows_focus','Focus a Windows desktop window.','CONTROL_COMPUTER',Risk.MEDIUM,{'type':'object','properties':{'title':{'type':'string'},'title_re':{'type':'string'}}},ui.focus)
reg('windows_click','Click a UI Automation control.','CONTROL_COMPUTER',Risk.MEDIUM,{'type':'object','properties':{'control_type':{'type':'string'},'title':{'type':'string'},'title_re':{'type':'string'},'window_title':{'type':'string'},'window_re':{'type':'string'}}},ui.click)
reg('windows_type','Type text into a UI Automation control.','CONTROL_COMPUTER',Risk.MEDIUM,{'type':'object','properties':{'text':{'type':'string'},'control_type':{'type':'string'},'title':{'type':'string'},'title_re':{'type':'string'},'window_title':{'type':'string'},'window_re':{'type':'string'},'clear':{'type':'boolean'}},'required':['text']},ui.type_text)
reg('windows_hotkey','Send a Windows hotkey sequence.','CONTROL_COMPUTER',Risk.MEDIUM,{'type':'object','properties':{'keys':{'type':'array','items':{'type':'string'}}},'required':['keys']},lambda keys:ui.hotkey(*keys))

async def search_web(query,count=5):
    if not web.enabled:return {'status':'FAILURE','error':'web search not configured'}
    results=await web.search(query,max(1,min(int(count),20)))
    for x in results:store.fact(x.get('title',''),'brave',x.get('url',''),.6,{'description':x.get('description',''),'query':query})
    return {'status':'SUCCESS','results':results}
reg('web_search','Search live public web.','INTERNET_SEARCH',Risk.LOW,{'type':'object','properties':{'query':{'type':'string'},'count':{'type':'integer'}},'required':['query']},search_web)
reg('browser_extract','Extract visible text from a public page.','INTERNET_SEARCH',Risk.MEDIUM,{'type':'object','properties':{'url':{'type':'string'}},'required':['url']},browser.extract)
reg('email_send','Send email through configured SMTP.','SEND_EMAIL',Risk.HIGH,{'type':'object','properties':{'to':{'type':'string'},'subject':{'type':'string'},'body':{'type':'string'}},'required':['to','subject','body']},emailc.send,True)
reg('email_search','Search configured mailbox.','READ_EMAIL',Risk.LOW,{'type':'object','properties':{'mailbox':{'type':'string'},'criteria':{'type':'string'},'limit':{'type':'integer'}}},emailc.search)
reg('calendar_parse','Parse local ICS.','READ_CALENDAR',Risk.LOW,{'type':'object','properties':{'path':{'type':'string'}},'required':['path']},lambda path:{'status':'SUCCESS','events':calendarc.parse(WS.path(path))})
reg('voice_transcribe','Transcribe an audio recording using the configured STT provider.','MEDIA',Risk.LOW,{'type':'object','properties':{'path':{'type':'string'},'language':{'type':'string'}},'required':['path']},lambda path,language='':media.transcribe(WS.path(path).read_bytes(),'audio/webm',language))
reg('voice_speak','Generate speech with the configured TTS provider.','MEDIA',Risk.LOW,{'type':'object','properties':{'text':{'type':'string'},'voice':{'type':'string'}},'required':['text']},media.speak)
reg('perception_observe','Analyze a supplied visual frame with the configured vision model.','PERCEPTION',Risk.MEDIUM,{'type':'object','properties':{'path':{'type':'string'},'prompt':{'type':'string'}},'required':['path']},lambda path,prompt='':media.perceive(WS.path(path).read_bytes(),prompt or 'Describe the visible scene and identify only observable evidence.'))
reg('self_inspect','Inspect the NOTSIP repository inventory and hashes.','SELF_MAINTENANCE',Risk.LOW,{'type':'object','properties':{}},lambda:{'status':'SUCCESS','repository':str(ROOT),'files':maint.inventory()})
reg('self_read','Read one NOTSIP source/config file.','SELF_MAINTENANCE',Risk.LOW,{'type':'object','properties':{'path':{'type':'string'}},'required':['path']},lambda path:{'status':'SUCCESS','path':path,'content':maint.read(path)})
reg('self_verify','Compile and test NOTSIP.','SELF_MAINTENANCE',Risk.MEDIUM,{'type':'object','properties':{}},lambda:maint.verify())
reg('self_apply','Apply a verified self-maintenance patch.','SELF_MAINTENANCE',Risk.HIGH,{'type':'object','properties':{'patch':{'type':'string'},'confirmation':{'type':'string'}},'required':['patch','confirmation']},lambda patch,confirmation:maint.apply_patch(patch,confirmation),True)
reg('make_plan','Build a verified model-independent action plan.','INTELLIGENCE',Risk.LOW,{'type':'object','properties':{'objective':{'type':'string'}},'required':['objective']},intellect.plan)
reg('corroborate','Find supporting evidence already stored by NOTSIP.','INTELLIGENCE',Risk.LOW,{'type':'object','properties':{'query':{'type':'string'}},'required':['query']},intellect.corroborate)
reg('find_contradictions','Find contradictory world relations.','INTELLIGENCE',Risk.LOW,{'type':'object','properties':{'entity':{'type':'string'}}},intellect.contradictions)
reg('trigger_candidates','Find durable memories that may warrant proactive follow-up.','INTELLIGENCE',Risk.LOW,{'type':'object','properties':{}},intellect.trigger_candidates)

auth_token=settings.api_key
async def require_auth(request:Request):
    if auth.mode=='oidc':
        cookie=request.cookies.get('notsip_session'); bearer=request.headers.get('authorization','')
        if cookie and auth.validate_session(cookie): return
        if bearer.startswith('Bearer ') and bearer[7:]==settings.api_key:return
        raise HTTPException(401,'OIDC authentication required')
    if auth_token and request.headers.get('authorization')!='Bearer '+auth_token:raise HTTPException(401,'Unauthorized')

class Message(BaseModel):message:str
class TaskIn(BaseModel):objective:str;handler:str='agent';delay:float=0;interval:float|None=None;data:dict=Field(default_factory=dict);priority:int=0
class PairIn(BaseModel):code:str;device_id:str;name:str;platform:str;public_key:str=''
class QueueCommand(BaseModel):action:str;payload:dict=Field(default_factory=dict)
class ResultIn(BaseModel):command_id:str;status:str;result:dict=Field(default_factory=dict)
class SelfPatch(BaseModel):patch:str;confirmation:str
class NodeIn(BaseModel):node_id:str;name:str;platform:str;capabilities:list[str]=Field(default_factory=list);public_key:str=''
class NodeBeat(BaseModel):token:str;capabilities:list[str]=Field(default_factory=list);health:dict=Field(default_factory=dict)
class PerceptionFrame(BaseModel):image_base64:str;mime:str='image/jpeg';prompt:str='Describe the visible scene and identify only observable evidence.'
class OIDCExchange(BaseModel):code:str;state:str

app=FastAPI(title='NOTSIP',version='0.9.0')
async def scheduled_agent(task):return await agent.handle(task['objective'])
jobs.register('agent',scheduled_agent); jobs.register('self_verify',lambda task:asyncio.to_thread(maint.verify)); jobs.register('checkpoint',lambda task:asyncio.to_thread(recovery.checkpoint,{'tasks':store.tasks(),'devices':store.devices(),'world':world.snapshot()}))

@app.on_event('startup')
async def startup(): app.state.worker=asyncio.create_task(jobs.loop())
@app.on_event('shutdown')
async def shutdown(): jobs.stop(); w=getattr(app.state,'worker',None); w and w.cancel()
@app.get('/')
async def root():
    ui=ROOT/'ui.html'; return FileResponse(ui) if ui.exists() else JSONResponse({'name':'NOTSIP','version':'0.9.0','status':'online'})
@app.get('/api/health')
async def health(_:None=Depends(require_auth)):return {'status':'ok','identity':'NOTSIP','version':'0.9.0','llm':provider.enabled,'fallback_llm':provider.fallback_enabled,'voice':bool(settings.stt_base_url and settings.stt_model and settings.tts_base_url and settings.tts_model),'vision':settings.vision_enabled,'scheduler':True,'federation':True}
@app.get('/api/status')
async def status(_:None=Depends(require_auth)):return {'identity':'NOTSIP','version':'0.9.0','autonomy_level':policy.level,'tools':[t.name for t in registry.all()],'devices':store.devices(),'world':world.snapshot(),'tasks':store.tasks(),'capabilities':{'llm':provider.enabled,'fallback_llm':provider.fallback_enabled,'voice_stt':bool(settings.stt_base_url and settings.stt_model),'voice_tts':bool(settings.tts_base_url and settings.tts_model),'vision':settings.vision_enabled,'windows_uia':True,'web_search':web.enabled,'email':emailc.enabled,'oidc':auth.oidc.configured,'android_pairing':True,'self_maintenance':True,'distributed_nodes':True,'recovery_checkpoints':True}}
@app.get('/api/degraded')
async def degraded(_:None=Depends(require_auth)):
    reasons=[]
    if not provider.enabled and not provider.fallback_enabled: reasons.append('llm_provider_not_configured')
    if not settings.stt_base_url or not settings.stt_model: reasons.append('stt_not_configured')
    if not settings.tts_base_url or not settings.tts_model: reasons.append('tts_not_configured')
    if not settings.vision_enabled: reasons.append('vision_disabled')
    if not web.enabled: reasons.append('web_search_not_configured')
    if not emailc.enabled: reasons.append('email_not_configured')
    if not auth.oidc.configured and auth.mode=='oidc': reasons.append('oidc_not_configured')
    return {'degraded':bool(reasons),'reasons':reasons}
@app.post('/api/message')
async def message(body:Message,_:None=Depends(require_auth)):return await agent.handle(body.message)
@app.get('/api/memory')
async def memory(q:str='',limit:int=20,_:None=Depends(require_auth)):return {'memories':store.memories(agent.user,max(1,min(int(limit),100)))}
@app.get('/api/facts')
async def facts(limit:int=100,_:None=Depends(require_auth)):return {'facts':store.facts(max(1,min(int(limit),500)))}
@app.get('/api/world')
async def world_api(_:None=Depends(require_auth)):return world.snapshot()
@app.get('/api/intelligence/plan')
async def plan(objective:str,_:None=Depends(require_auth)):return intellect.plan(objective)
@app.get('/api/intelligence/corroborate')
async def corroborate(q:str,_:None=Depends(require_auth)):return {'evidence':intellect.corroborate(q)}
@app.get('/api/intelligence/contradictions')
async def contradictions(entity:str='',_:None=Depends(require_auth)):return {'contradictions':intellect.contradictions(entity or None)}
@app.get('/api/intelligence/triggers')
async def triggers(_:None=Depends(require_auth)):return {'candidates':intellect.trigger_candidates()}
@app.get('/api/audit')
async def audit_api(_:None=Depends(require_auth)):return {'audit':store.audit_recent()}
@app.get('/api/tasks')
async def tasks(_:None=Depends(require_auth)):return {'tasks':store.tasks()}
@app.post('/api/tasks')
async def create_task(body:TaskIn,_:None=Depends(require_auth)):
    if body.handler not in jobs.handlers:raise HTTPException(400,f'unknown task handler: {body.handler}')
    return {'task_id':jobs.create(body.objective,body.handler,body.delay,body.interval,body.data,body.priority),'handler':body.handler}
@app.post('/api/tasks/{task_id}/run')
async def run_task(task_id:str,_:None=Depends(require_auth)):
    if not store.row('SELECT id FROM tasks WHERE id=?',(task_id,)):raise HTTPException(404,'Task not found')
    store.task_update(task_id,state='PENDING',run_at=0);return {'status':'QUEUED','task_id':task_id}
@app.get('/api/pair/code')
async def pair_code(_:None=Depends(require_auth)):return {'code':pairing.create_code()}
@app.post('/api/pair/consume')
async def pair_consume(body:PairIn):
    token=pairing.consume(body.code,body.device_id,body.name,body.platform,body.public_key)
    if not token:raise HTTPException(400,'Invalid or expired pairing code')
    return {'paired':True,'device_id':body.device_id,'token':token}
@app.get('/api/devices')
async def devices(_:None=Depends(require_auth)):return {'devices':store.devices()}
@app.get('/api/devices/{device_id}/commands')
async def commands(device_id:str,token:str):
    if not store.device_token_valid(device_id,token):raise HTTPException(401,'Invalid device token')
    return {'commands':store.pull_commands(device_id)}
@app.post('/api/devices/{device_id}/commands')
async def queue_command(device_id:str,body:QueueCommand,_:None=Depends(require_auth)):
    if not store.row('SELECT id FROM devices WHERE id=?',(device_id,)):raise HTTPException(404,'Device not paired')
    d=policy.decide(Risk.MEDIUM)
    if not d.allowed:return {'status':'PARTIAL_SUCCESS','approval_required':d.needs_confirmation,'error':d.reason}
    return {'status':'SUCCESS','command_id':store.queue_command(device_id,body.action,body.payload)}
@app.post('/api/devices/result')
async def command_result(body:ResultIn):
    if not store.row('SELECT id FROM commands WHERE id=?',(body.command_id,)):raise HTTPException(404,'Command not found')
    store.command_result(body.command_id,body.status,body.result);return {'status':'SUCCESS'}
@app.post('/api/federation/register')
async def federation_register(body:NodeIn,_:None=Depends(require_auth)):return nodes.register(body.node_id,body.name,body.platform,body.capabilities,body.public_key)
@app.post('/api/federation/{node_id}/heartbeat')
async def federation_heartbeat(node_id:str,body:NodeBeat):return {'status':'SUCCESS','lease':nodes.heartbeat(node_id,body.token,body.capabilities,body.health)}
@app.get('/api/federation/nodes')
async def federation_nodes(_:None=Depends(require_auth)):return {'nodes':nodes.reconcile()}
@app.get('/api/federation/recovery-plan')
async def federation_recovery(_:None=Depends(require_auth)):return nodes.recovery_plan()
@app.post('/api/recovery/checkpoint')
async def checkpoint(_:None=Depends(require_auth)):return {'status':'SUCCESS','path':recovery.checkpoint({'tasks':store.tasks(),'devices':store.devices(),'world':world.snapshot(),'timestamp':time.time()})}
@app.get('/api/recovery/latest')
async def latest_checkpoint(_:None=Depends(require_auth)):return {'checkpoint':recovery.latest()}
@app.post('/api/voice/transcribe')
async def transcribe(file:UploadFile=File(...),language:str='',_:None=Depends(require_auth)):
    return await media.transcribe(await file.read(),file.content_type or 'audio/webm',language or settings.stt_language)
@app.post('/api/voice/speak')
async def speak(body:dict,_:None=Depends(require_auth)):return await media.speak(str(body.get('text','')),str(body.get('voice','')))
@app.post('/api/perception/frame')
async def perception(body:PerceptionFrame,_:None=Depends(require_auth)):
    try:blob=base64.b64decode(body.image_base64,validate=True)
    except Exception as e:raise HTTPException(400,'invalid image_base64') from e
    result=await media.perceive(blob,body.prompt,body.mime); store.remember('primary-user','perception',result['observation'],.7,'vision',{'frame':result['frame']}); return result
@app.get('/api/email/status')
async def email_status(_:None=Depends(require_auth)):return {'configured':emailc.enabled,'smtp':bool(emailc.smtp_host),'imap':bool(emailc.imap_host),'username_configured':bool(emailc.username)}
@app.post('/api/email/send')
async def email_send(body:dict,_:None=Depends(require_auth)):
    d=policy.decide(Risk.HIGH)
    if not d.allowed:return {'status':'PARTIAL_SUCCESS','approval_required':d.needs_confirmation,'error':d.reason}
    return emailc.send(body['to'],body['subject'],body['body'])
@app.get('/api/email/search')
async def email_search(mailbox='INBOX',criteria='ALL',limit=20,_:None=Depends(require_auth)):
    if not emailc.imap_host:raise HTTPException(503,'IMAP not configured')
    return emailc.search(mailbox,criteria,max(1,min(int(limit),50)))
@app.get('/api/search')
async def search(q:str,count:int=5,_:None=Depends(require_auth)):
    if not web.enabled:raise HTTPException(503,'Web search not configured')
    return {'results':await web.search(q,max(1,min(int(count),20)))}
@app.get('/api/oauth/status')
async def oidc_status(_:None=Depends(require_auth)):return {'mode':auth.mode,'configured':auth.oidc.configured,'provider':settings.oidc_provider,'issuer':auth.oidc.issuer,'client_id_configured':bool(auth.oidc.client_id),'redirect_uri':auth.oidc.redirect_uri}
@app.get('/api/oauth/login')
async def oidc_login(request:Request):
    if not auth.oidc.configured:raise HTTPException(503,'OIDC is not configured')
    verifier,challenge=pkce_pair(); state=secrets.token_urlsafe(32); auth.sessions['oidc:'+state]={'verifier':verifier,'expires':time.time()+600}
    url=await auth.oidc.authorize_url(state,challenge); return RedirectResponse(url)
@app.get('/api/oauth/callback')
async def oidc_callback(code:str,state:str):
    pending=auth.sessions.pop('oidc:'+state,None)
    if not pending or pending.get('expires',0)<time.time():raise HTTPException(400,'invalid or expired OIDC state')
    tokens=await auth.oidc.exchange(code,pending['verifier']); claims=await auth.oidc.userinfo(tokens.get('access_token','')) if tokens.get('access_token') else {}
    session=auth.mint_session({'claims':claims,'tokens':tokens}); r=RedirectResponse('/'); r.set_cookie('notsip_session',session,httponly=True,secure=bool(settings.oidc_redirect_uri.startswith('https://')),samesite='lax',max_age=settings.session_ttl); return r
@app.post('/api/oauth/logout')
async def oidc_logout(request:Request):
    s=request.cookies.get('notsip_session'); auth.sessions.pop(s,None) if s else None; r=Response(status_code=204); r.delete_cookie('notsip_session'); return r
@app.get('/api/auth/me')
async def auth_me(request:Request,_:None=Depends(require_auth)):return {'mode':auth.mode,'authenticated':True,'claims':auth.sessions.get(request.cookies.get('notsip_session'),{}).get('claims',{})}
@app.post('/api/events')
async def ingest_event(request:Request,x_notsip_signature:str|None=Header(default=None),_:None=Depends(require_auth)):
    raw=await request.body(); secret=settings.event_hmac_secret.encode()
    if secret:
        if not x_notsip_signature:raise HTTPException(401,'event signature required')
        expected=hmac.new(secret,raw,hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,x_notsip_signature):raise HTTPException(401,'invalid event signature')
    p=json.loads(raw); event=Event(p.get('type','external.event'),p.get('payload',{}),p.get('source','external')); await events.publish(event); return {'accepted':True,'event_type':event.type}
@app.get('/api/self/inspect')
async def self_inspect(_:None=Depends(require_auth)):return {'identity':'NOTSIP','repository':str(ROOT),'files':maint.inventory()}
@app.get('/api/self/verify')
async def self_verify(_:None=Depends(require_auth)):return maint.verify()
@app.get('/api/self/read')
async def self_read(path:str,_:None=Depends(require_auth)):return {'path':path,'content':maint.read(path)}
@app.post('/api/self/apply')
async def self_apply(body:SelfPatch,_:None=Depends(require_auth)):
    if not settings.self_modify_enabled:return {'status':'PARTIAL_SUCCESS','approval_required':True,'error':'self-modification is disabled by configuration'}
    d=policy.decide(Risk.HIGH)
    if not d.allowed:return {'status':'PARTIAL_SUCCESS','approval_required':True,'error':d.reason}
    result=maint.apply_patch(body.patch,body.confirmation); store.audit('primary-user','self-maintenance','apply patch','self_maintenance','execute',json.dumps(result,default=str)); return result
@app.websocket('/ws/events')
async def ws(sock:WebSocket):
    if auth_token and sock.headers.get('authorization')!='Bearer '+auth_token:await sock.close(code=4401);return
    await sock.accept(); q=events.subscribe()
    try:
        while True:
            e=await q.get(); await sock.send_json({'type':e.type,'payload':e.payload,'source':e.source,'timestamp':e.timestamp})
    except WebSocketDisconnect:pass
    finally:events.unsubscribe(q)
