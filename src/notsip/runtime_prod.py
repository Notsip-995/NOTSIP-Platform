from __future__ import annotations
import asyncio,base64,hashlib,hmac,json,secrets,time
from pathlib import Path
from fastapi import Depends,FastAPI,File,Header,HTTPException,Request,UploadFile,WebSocket,WebSocketDisconnect
from fastapi.responses import FileResponse,JSONResponse,RedirectResponse,Response
from pydantic import BaseModel,Field
from .config import settings
from .store import Store
from .policy import Policy,Risk
from .provider import Provider
from .tools import Registry,Tool,Workspace,Windows,calc,open_target
from .connectors import Web,Email,Calendar,Browser
from .world import WorldModel
from .jobs import Scheduler
from .android_bridge import Pairing
from .agent import Agent
from .events import Event,EventBus
from .self_maintenance import SelfMaintenance
from .windows_automation import WindowsAutomation
from .media import MediaEngine
from .nodes import NodeRegistry,RecoveryManager
from .intelligence import Intelligence
from .security import AuthManager,pkce_pair
from .oauth_services import OAuthService

settings.ensure();DATA=Path(settings.data_dir).resolve();ROOT=Path(__file__).resolve().parents[2];WS=Workspace(DATA/'workspace')
store=Store(DATA,settings.database_url);policy=Policy(settings.autonomy_level);registry=Registry();events=EventBus();provider=Provider(settings.llm_base_url,settings.llm_api_key,settings.llm_model,settings.fallback_llm_base_url,settings.fallback_llm_api_key,settings.fallback_llm_model)
world=WorldModel(store);jobs=Scheduler(store);win=Windows(WS);uia=WindowsAutomation();web=Web(settings.brave_api_key);browser=Browser();emailc=Email(settings.smtp_host,settings.smtp_port,settings.imap_host,settings.email_username,settings.email_password);calendarc=Calendar();pairing=Pairing(store)
agent=Agent(settings,store,policy,registry,provider,world);maint=SelfMaintenance(ROOT);media=MediaEngine(settings,provider,DATA);nodes=NodeRegistry(store,settings.node_shared_secret);recovery=RecoveryManager(DATA);intellect=Intelligence(store,world);auth=AuthManager(settings,DATA);oauth=OAuthService(auth.secrets)

def reg(name,desc,cap,risk,schema,fn,destructive=False):registry.add(Tool(name,desc,cap,risk,schema,fn,destructive))
reg('calculator','Safe arithmetic.','COMPUTE',Risk.LOW,{'type':'object','properties':{'expr':{'type':'string'}},'required':['expr']},calc)
reg('list_files','List authorized workspace files.','READ_FILES',Risk.LOW,{'type':'object','properties':{'query':{'type':'string'}}},lambda query='':{'status':'SUCCESS','files':WS.list(query)})
reg('read_file','Read authorized workspace text.','READ_FILES',Risk.LOW,{'type':'object','properties':{'path':{'type':'string'}},'required':['path']},lambda path:{'status':'SUCCESS','content':WS.read(path)})
reg('write_file','Write authorized workspace text.','WRITE_FILES',Risk.MEDIUM,{'type':'object','properties':{'path':{'type':'string'},'content':{'type':'string'}},'required':['path','content']},lambda path,content:{'status':'SUCCESS','path':WS.write(path,content)})
reg('windows_exec','Execute PowerShell on Windows.','CONTROL_COMPUTER',Risk.HIGH,{'type':'object','properties':{'command':{'type':'string'},'timeout':{'type':'integer','minimum':1,'maximum':180}},'required':['command']},win.exec,True)
reg('desktop_screenshot','Capture the primary Windows desktop.','CONTROL_COMPUTER',Risk.MEDIUM,{'type':'object','properties':{'filename':{'type':'string'}}},win.screenshot)
reg('open_target','Open a Windows URL, file, or application.','CONTROL_COMPUTER',Risk.MEDIUM,{'type':'object','properties':{'target':{'type':'string'}},'required':['target']},open_target)
reg('windows_list','List visible Windows UIA windows.','CONTROL_COMPUTER',Risk.MEDIUM,{'type':'object','properties':{'title_re':{'type':'string'}},},uia.windows)
reg('windows_focus','Focus a Windows UIA window.','CONTROL_COMPUTER',Risk.MEDIUM,{'type':'object','properties':{'title':{'type':'string'},'title_re':{'type':'string'}},'required':['title']},uia.focus)
reg('windows_click','Click a Windows UIA control.','CONTROL_COMPUTER',Risk.MEDIUM,{'type':'object','properties':{'control_type':{'type':'string'},'title':{'type':'string'},'title_re':{'type':'string'},'window_title':{'type':'string'},'window_re':{'type':'string'}}},uia.click)
reg('windows_type','Type into a Windows UIA control.','CONTROL_COMPUTER',Risk.MEDIUM,{'type':'object','properties':{'text':{'type':'string'},'control_type':{'type':'string'},'title':{'type':'string'},'title_re':{'type':'string'},'window_title':{'type':'string'},'window_re':{'type':'string'},'clear':{'type':'boolean'}},'required':['text']},uia.type_text)
reg('windows_hotkey','Send a Windows hotkey sequence.','CONTROL_COMPUTER',Risk.MEDIUM,{'type':'object','properties':{'keys':{'type':'array','items':{'type':'string'}}},'required':['keys']},lambda keys:uia.hotkey(*keys))
async def web_search(query,count=5):
    if not web.enabled:return {'status':'FAILURE','error':'web search not configured'}
    result=await web.search(query,max(1,min(int(count),20)))
    for item in result:store.fact(item.get('title',''),'brave',item.get('url',''),.6,{'query':query,'description':item.get('description','')})
    return {'status':'SUCCESS','results':result}
reg('web_search','Search live public web.','INTERNET_SEARCH',Risk.LOW,{'type':'object','properties':{'query':{'type':'string'},'count':{'type':'integer'}},'required':['query']},web_search)
reg('browser_extract','Extract visible text from a public web page.','INTERNET_SEARCH',Risk.MEDIUM,{'type':'object','properties':{'url':{'type':'string'}},'required':['url']},browser.extract)
reg('email_send','Send email through configured SMTP.','SEND_EMAIL',Risk.HIGH,{'type':'object','properties':{'to':{'type':'string'},'subject':{'type':'string'},'body':{'type':'string'}},'required':['to','subject','body']},emailc.send,True)
reg('email_search','Search configured mailbox.','READ_EMAIL',Risk.LOW,{'type':'object','properties':{'mailbox':{'type':'string'},'criteria':{'type':'string'},'limit':{'type':'integer'}}},emailc.search)
reg('calendar_parse','Parse local ICS.','READ_CALENDAR',Risk.LOW,{'type':'object','properties':{'path':{'type':'string'}},'required':['path']},lambda path:{'status':'SUCCESS','events':calendarc.parse(WS.path(path))})
reg('voice_transcribe','Transcribe an audio file via STT.','MEDIA',Risk.LOW,{'type':'object','properties':{'path':{'type':'string'},'language':{'type':'string'}},'required':['path']},lambda path,language='':media.transcribe(WS.path(path).read_bytes(),'audio/webm',language or settings.stt_language))
reg('voice_speak','Generate speech with TTS.','MEDIA',Risk.LOW,{'type':'object','properties':{'text':{'type':'string'},'voice':{'type':'string'}},'required':['text']},media.speak)
reg('perception_observe','Analyze a visual frame.','PERCEPTION',Risk.MEDIUM,{'type':'object','properties':{'path':{'type':'string'},'prompt':{'type':'string'}},'required':['path']},lambda path,prompt='':media.perceive(WS.path(path).read_bytes(),prompt or 'Describe visible evidence only.'))
reg('self_inspect','Inspect NOTSIP repository and SHA-256 manifest.','SELF_MAINTENANCE',Risk.LOW,{'type':'object','properties':{}},lambda:{'status':'SUCCESS','repository':str(ROOT),'files':maint.inventory()})
reg('self_read','Read a NOTSIP source/config file.','SELF_MAINTENANCE',Risk.LOW,{'type':'object','properties':{'path':{'type':'string'}},'required':['path']},lambda path:{'status':'SUCCESS','path':path,'content':maint.read(path)})
reg('self_verify','Compile and run NOTSIP tests.','SELF_MAINTENANCE',Risk.MEDIUM,{'type':'object','properties':{}},lambda:maint.verify())
reg('self_apply','Apply a verified self-maintenance patch.','SELF_MAINTENANCE',Risk.HIGH,{'type':'object','properties':{'patch':{'type':'string'},'confirmation':{'type':'string'}},'required':['patch','confirmation']},lambda patch,confirmation:maint.apply_patch(patch,confirmation),True)
reg('make_plan','Build a model-independent execution plan.','INTELLIGENCE',Risk.LOW,{'type':'object','properties':{'objective':{'type':'string'}},'required':['objective']},intellect.plan)
reg('corroborate','Find supporting stored evidence.','INTELLIGENCE',Risk.LOW,{'type':'object','properties':{'query':{'type':'string'}},'required':['query']},intellect.corroborate)
reg('find_contradictions','Find contradictory world relations.','INTELLIGENCE',Risk.LOW,{'type':'object','properties':{'entity':{'type':'string'}}},intellect.contradictions)
reg('trigger_candidates','Find memories that may warrant proactive follow-up.','INTELLIGENCE',Risk.LOW,{'type':'object','properties':{}},intellect.trigger_candidates)

def android_command(device_id,action,payload=None):
    x=store.row('SELECT id,status FROM devices WHERE id=?',(device_id,))
    if not x:raise ValueError('Android/device is not paired')
    if x.get('status')=='REVOKED':raise PermissionError('device is revoked')
    allowed={'open_url','open_app','notify','click_text','make_call','send_sms'}
    if action not in allowed:raise ValueError(f'unsupported Android action: {action}')
    cid=store.queue_command(device_id,action,payload or {})
    return {'status':'QUEUED','command_id':cid,'device_id':device_id,'action':action}
reg('android_command','Queue an authorized command on a paired Android device; call/SMS are high-risk and require approval.','ANDROID_CONTROL',Risk.HIGH,{'type':'object','properties':{'device_id':{'type':'string'},'action':{'type':'string'},'payload':{'type':'object'}},'required':['device_id','action']},android_command,True)

auth_token=settings.api_key
async def require_auth(request:Request):
    if auth.mode=='oidc':
        cookie=request.cookies.get('notsip_session')
        if cookie and auth.validate_session(cookie):return
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

app=FastAPI(title='NOTSIP',version='0.9.0')
async def scheduled_agent(task):return await agent.handle(task['objective'])
jobs.register('agent',scheduled_agent);jobs.register('self_verify',lambda task:asyncio.to_thread(maint.verify));jobs.register('checkpoint',lambda task:asyncio.to_thread(recovery.checkpoint,{'tasks':store.tasks(),'devices':store.devices(),'world':world.snapshot(),'timestamp':time.time()}))
@app.on_event('startup')
async def startup():app.state.worker=asyncio.create_task(jobs.loop())
@app.on_event('shutdown')
async def shutdown():jobs.stop();w=getattr(app.state,'worker',None);w and w.cancel()
@app.get('/')
async def root():
    ui=ROOT/'ui.html';return FileResponse(ui) if ui.exists() else JSONResponse({'name':'NOTSIP','version':'0.9.0','status':'online'})
@app.get('/api/health')
async def health(_:None=Depends(require_auth)):return {'status':'ok','identity':'NOTSIP','version':'0.9.0','llm':provider.enabled,'fallback_llm':provider.fallback_enabled,'voice_stt':bool(settings.stt_base_url and settings.stt_model),'voice_tts':bool(settings.tts_base_url and settings.tts_model),'vision':settings.vision_enabled,'windows_uia':True,'scheduler':True,'federation':True,'recovery':True}
@app.get('/api/status')
async def status(_:None=Depends(require_auth)):return {'identity':'NOTSIP','version':'0.9.0','autonomy_level':policy.level,'tools':[t.name for t in registry.all()],'devices':store.devices(),'world':world.snapshot(),'tasks':store.tasks(),'capabilities':{'llm':provider.enabled,'fallback_llm':provider.fallback_enabled,'voice_stt':bool(settings.stt_base_url and settings.stt_model),'voice_tts':bool(settings.tts_base_url and settings.tts_model),'vision':settings.vision_enabled,'windows_uia':True,'web_search':web.enabled,'email':emailc.enabled,'oidc':auth.oidc.configured,'android_pairing':True,'self_maintenance':settings.self_modify_enabled,'distributed_nodes':True,'recovery_checkpoints':True}}
@app.get('/api/degraded')
async def degraded(_:None=Depends(require_auth)):
    reasons=[]
    if not provider.enabled and not provider.fallback_enabled:reasons.append('llm_provider_not_configured')
    if not settings.stt_base_url or not settings.stt_model:reasons.append('stt_not_configured')
    if not settings.tts_base_url or not settings.tts_model:reasons.append('tts_not_configured')
    if not settings.vision_enabled:reasons.append('vision_disabled')
    if not web.enabled:reasons.append('web_search_not_configured')
    if not emailc.enabled:reasons.append('email_not_configured')
    if auth.mode=='oidc' and not auth.oidc.configured:reasons.append('oidc_not_configured')
    return {'degraded':bool(reasons),'reasons':reasons}
@app.post('/api/message')
async def message(body:Message,_:None=Depends(require_auth)):return await agent.handle(body.message)
@app.get('/api/memory')
async def memory(q:str='',limit:int=20,_:None=Depends(require_auth)):return {'memories':store.memories(agent.user,q,max(1,min(int(limit),100)))}
@app.get('/api/facts')
async def facts(limit:int=100,_:None=Depends(require_auth)):return {'facts':store.facts(max(1,min(int(limit),500)))}
@app.get('/api/world')
async def world_state(_:None=Depends(require_auth)):return world.snapshot()
@app.get('/api/intelligence/plan')
async def plan(objective:str,_:None=Depends(require_auth)):return intellect.plan(objective)
@app.get('/api/intelligence/corroborate')
async def corroborate(q:str,_:None=Depends(require_auth)):return {'evidence':intellect.corroborate(q)}
@app.get('/api/intelligence/contradictions')
async def contradictions(entity:str='',_:None=Depends(require_auth)):return {'contradictions':intellect.contradictions(entity or None)}
@app.get('/api/intelligence/triggers')
async def triggers(_:None=Depends(require_auth)):return {'candidates':intellect.trigger_candidates()}
@app.get('/api/audit')
async def audit(_:None=Depends(require_auth)):return {'audit':store.audit_recent()}
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