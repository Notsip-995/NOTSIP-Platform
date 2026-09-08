from __future__ import annotations
import json, os, socket, time, uuid, inspect, copy, secrets
from pathlib import Path
from fastapi import Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from .runtime_prod import app, media, settings, store, nodes, recovery, intellect, events, web, emailc, require_auth, auth, provider, pairing, uia, win, registry, agent
from .runtime_prod import policy
from .provider import Provider
from .connectors import Web, Email
from .security import OIDCProvider
from .policy import Policy, Risk
from .nodes import NodeRegistry
from .streaming import attach as attach_streaming
from .background import attach as attach_background
from .routes_extra import attach as attach_extra
from .perception_loop import attach as attach_perception
from .product_layer import resource_root, repo_root, ConfigStore, AuditLog, BackupManager, ApprovalStore, Diagnostics, Maintenance, CapabilityProbe
from .memory_service import MemoryService
from .account_store import AccountStore
from .conversations import ConversationStore
from .logging_setup import configure as configure_logging
from .native_voice import NativeVoiceWorker
from .tools import Tool
from .execution_gate import ToolExecutionGate

attach_streaming(app,media,settings,settings.api_key)
attach_extra(app,require_auth,web,emailc)
PRODUCT_ROOT=repo_root();DATA=Path(settings.data_dir).resolve();config_store=ConfigStore(DATA);audit_log=AuditLog(DATA);backups=BackupManager(DATA);approvals=ApprovalStore(DATA);diagnostics=Diagnostics(DATA,settings,store,provider,web,emailc,auth,nodes,recovery);maintenance=Maintenance(PRODUCT_ROOT);probes=CapabilityProbe(settings,store,provider,web,emailc);memory_service=MemoryService(store);accounts=AccountStore(auth.secrets);conversations=ConversationStore(DATA);logger=configure_logging(DATA,settings.log_level,settings.log_max_bytes,settings.log_backup_count);native_voice=NativeVoiceWorker(settings,media,events)

CONFIG_SECRET_NAMES={'api_key','event_hmac_secret','pairing_secret','llm_api_key','fallback_llm_api_key','stt_api_key','tts_api_key','email_password','oidc_client_secret','oauth_client_secret','node_shared_secret','brave_api_key','flight_planning_token','remote_compute_token','remote_sensing_token','home_adapter_token','biometric_adapter_token'}
CONFIG_HIGH_RISK={'host','port','auth_mode','oidc_issuer','oidc_client_id','oidc_redirect_uri','self_modify_enabled','capability_levels','github_update_enabled','windows_publisher_thumbprint',*CONFIG_SECRET_NAMES}

def _rebuild_runtime_after_config():
    global provider,web,emailc,policy,diagnostics,probes,auth_token
    provider=Provider(settings.llm_base_url,settings.llm_api_key,settings.llm_model,settings.fallback_llm_base_url,settings.fallback_llm_api_key,settings.fallback_llm_model)
    web=Web(settings.brave_api_key);emailc=Email(settings.smtp_host,settings.smtp_port,settings.imap_host,settings.email_username,settings.email_password);policy=Policy(settings.autonomy_level);nodes.secret=settings.node_shared_secret;agent.provider=provider;agent.policy=policy;auth_token=settings.api_key
    auth.settings=settings;auth.oidc=OIDCProvider(settings.oidc_provider,settings.oidc_issuer,settings.oidc_client_id,settings.oidc_client_secret,settings.oidc_redirect_uri,settings.oidc_scopes);diagnostics=Diagnostics(DATA,settings,store,provider,web,emailc,auth,nodes,recovery);probes=CapabilityProbe(settings,store,provider,web,emailc)

def _apply_config(requested):
    allowed={k for k in settings.__class__.model_fields.keys() if k not in CONFIG_SECRET_NAMES|{'database_url'}};snapshot={k:copy.deepcopy(getattr(settings,k)) for k in set(requested)|{'host','port','auth_mode','oidc_issuer','oidc_client_id','oidc_redirect_uri','self_modify_enabled','capability_levels','github_update_enabled','windows_publisher_thumbprint','database_url'}};secret_snapshot={k:auth.secrets.get('NOTSIP_'+k.upper()) for k in CONFIG_SECRET_NAMES if k in requested}
    try:
        for k,v in requested.items():
            if k in allowed:setattr(settings,k,v)
            elif k in CONFIG_SECRET_NAMES:auth.secrets.set('NOTSIP_'+k.upper(),str(v));setattr(settings,k,str(v))
        settings.ensure();config_store.save({k:getattr(settings,k) for k in allowed});_rebuild_runtime_after_config();audit_log.write('config.updated',keys=sorted(requested));return {'status':'SUCCESS','version':2,'changed':sorted(requested),'restart_required':False,'diagnostics':diagnostics.run()}
    except Exception as exc:
        for k,v in snapshot.items():setattr(settings,k,v)
        for k,v in secret_snapshot.items():
            if v is None:auth.secrets.delete('NOTSIP_'+k.upper())
            else:auth.secrets.set('NOTSIP_'+k.upper(),v)
        _rebuild_runtime_after_config();raise RuntimeError(f'configuration rejected: {exc}') from exc

def _config_admin(pending_id,keys):
    pending=auth.secrets.get('config:pending:'+str(pending_id))
    if not isinstance(pending,dict):raise RuntimeError('pending configuration change not found or expired')
    try:return _apply_config(pending)
    finally:auth.secrets.delete('config:pending:'+str(pending_id))

if registry.get('config_admin') is None:registry.add(Tool('config_admin','Authorize and apply security-sensitive configuration changes from an encrypted pending record.','SELF_MAINTENANCE',Risk.HIGH,{'type':'object','properties':{'pending_id':{'type':'string'},'keys':{'type':'array'}},'required':['pending_id','keys']},_config_admin,True))
if registry.get('backup_restore') is None:registry.add(Tool('backup_restore','Restore a verified NOTSIP backup after explicit confirmation.','SELF_MAINTENANCE',Risk.HIGH,{'type':'object','properties':{'name':{'type':'string'}},'required':['name']},lambda name:backups.restore(name,True),True))
if registry.get('native_voice_start') is None:registry.add(Tool('native_voice_start','Start the configured native microphone voice worker.','ACCESS_MICROPHONE',Risk.MEDIUM,{'type':'object','properties':{}},lambda:native_voice.start()))
if registry.get('native_voice_stop') is None:registry.add(Tool('native_voice_stop','Stop the configured native microphone voice worker.','ACCESS_MICROPHONE',Risk.MEDIUM,{'type':'object','properties':{}},lambda:native_voice.stop()))
ToolExecutionGate.wrap_registry(registry)
attach_background(app,store,nodes,recovery,intellect,events,memory_service,settings.health_interval,settings.checkpoint_interval,settings.proactive_interval,settings.memory_maintenance_interval)
attach_perception(app,settings,win,media,store,events)
app.router.routes=[r for r in app.router.routes if not (getattr(r,'path',None)=='/' and 'GET' in getattr(r,'methods',set()))]
@app.get('/',include_in_schema=False)
async def product_root():
    if not config_store.path.exists():return RedirectResponse('/setup',status_code=302)
    ui=resource_root()/'ui.html';return FileResponse(ui) if ui.exists() else JSONResponse({'name':'NOTSIP','version':'0.9.0','status':'online','error':'UI resource missing'})
@app.get('/setup',include_in_schema=False)
async def setup_page():
    p=resource_root()/'setup.html'
    if not p.exists():raise HTTPException(404,'setup UI missing')
    return FileResponse(p)
SESSION_KEY='runtime:browser_sessions'
def _sessions():return auth.secrets.get(SESSION_KEY,{}) or {}
def _save_sessions(d):auth.secrets.set(SESSION_KEY,d)
_old_mint=auth.mint_session
def _mint_persistent(claims):
    token=_old_mint(claims);d=_sessions();d[token]={'claims':claims,'expires':time.time()+settings.session_ttl};_save_sessions(d);return token
def _validate_persistent(token):
    d=_sessions();s=d.get(token)
    if not s or s.get('expires',0)<=time.time():
        if token in d:d.pop(token);_save_sessions(d)
        return False
    auth.sessions[token]=s;return True
auth.mint_session=_mint_persistent;auth.validate_session=_validate_persistent
_pair_attempts={}
def _rate_limited(ip:str,window=60,limit=15):
    now=time.time();recent=[t for t in _pair_attempts.get(ip,[]) if now-t<window];_pair_attempts[ip]=recent
    if len(recent)>=limit:return True
    recent.append(now);return False
@app.middleware('http')
async def production_security(request:Request,call_next):
    rid=request.headers.get('X-Request-ID') or uuid.uuid4().hex;request.state.request_id=rid
    cookie=request.cookies.get('notsip_session')
    if cookie and not request.headers.get('authorization') and auth.validate_session(cookie):request.scope['headers']=list(request.scope.get('headers',[]))+[(b'authorization',('Bearer '+settings.api_key).encode())]
    if request.url.path=='/api/devices/result':
        device_id=request.headers.get('X-NOTSIP-Device-ID','');device_token=request.headers.get('X-NOTSIP-Device-Token','')
        if not device_id or not device_token or not store.device_token_valid(device_id,device_token):return JSONResponse({'detail':'device authentication required'},status_code=401,headers={'X-Request-ID':rid})
    if request.url.path=='/api/pair/consume' and _rate_limited(request.client.host if request.client else 'unknown'):return JSONResponse({'detail':'pairing rate limit exceeded'},status_code=429,headers={'X-Request-ID':rid})
    try:response=await call_next(request)
    except Exception as exc:logger.exception('request failed');audit_log.write('request.error',request_id=rid,path=request.url.path,error=str(exc));raise
    response.headers['X-Request-ID']=rid;audit_log.write('request',request_id=rid,method=request.method,path=request.url.path,status=response.status_code);return response
@app.post('/api/login')
async def api_login(payload:dict):
    if not settings.api_key:raise HTTPException(503,'API key authentication is disabled; local access is open')
    if not secrets.compare_digest(str(payload.get('api_key','')),settings.api_key):raise HTTPException(401,'invalid API key')
    token=auth.mint_session({'mode':'api_key','sub':'primary-user'});r=JSONResponse({'authenticated':True});r.set_cookie('notsip_session',token,httponly=True,samesite='lax',secure=not str(settings.host) in {'127.0.0.1','::1','localhost'},max_age=settings.session_ttl);return r
@app.post('/api/logout')
async def api_logout(request:Request):
    s=request.cookies.get('notsip_session');d=_sessions();d.pop(s,None);_save_sessions(d);auth.sessions.pop(s,None);r=Response(status_code=204);r.delete_cookie('notsip_session');return r
@app.get('/api/capabilities')
async def capabilities(_:None=Depends(require_auth)):return {'configured':probes.snapshot(),'diagnostics':diagnostics.run(),'voice_native':native_voice.running}
@app.get('/api/diagnostics')
async def diagnostics_route(_:None=Depends(require_auth)):return diagnostics.run()
@app.get('/api/audit/log')
async def audit_log_route(_:None=Depends(require_auth)):return {'events':audit_log.tail()}
@app.get('/api/config')
async def config_get(_:None=Depends(require_auth)):
    data=config_store.load();data['settings']={k:v for k,v in data.get('settings',{}).items() if not any(x in k.lower() for x in ('key','password','secret','token'))};return data
@app.post('/api/config')
async def config_set(payload:dict,_:None=Depends(require_auth)):
    requested=dict(payload.get('settings') or {})
    if not requested:raise HTTPException(400,'settings are required')
    unknown=set(requested)-set(settings.__class__.model_fields)
    if unknown:raise HTTPException(400,f'unsupported settings: {sorted(unknown)}')
    sensitive=sorted(set(requested)&CONFIG_HIGH_RISK)
    if sensitive:
        pending_id=uuid.uuid4().hex
        auth.secrets.set('config:pending:'+pending_id,requested)
        result=await agent.run_tool('config_admin',{'pending_id':pending_id,'keys':sensitive})
        if result.get('status')=='FAILURE':auth.secrets.delete('config:pending:'+pending_id)
        return result
    try:return _apply_config(requested)
    except RuntimeError as exc:raise HTTPException(400,str(exc))
@app.post('/api/diagnostics/test-config')
async def test_config(_:None=Depends(require_auth)):return diagnostics.run()
@app.post('/api/backups')
async def create_backup(_:None=Depends(require_auth)):return backups.create()
@app.get('/api/backups')
async def list_backups(_:None=Depends(require_auth)):return {'backups':backups.list()}
@app.get('/api/backups/{name}/verify')
async def verify_backup(name:str,_:None=Depends(require_auth)):return backups.verify(name)
@app.post('/api/backups/{name}/restore')
async def restore_backup(name:str,payload:dict,_:None=Depends(require_auth)):
    if not payload.get('confirm'):raise HTTPException(400,'restore confirmation required')
    return await agent.run_tool('backup_restore',{'name':name})
@app.get('/api/approvals')
async def approvals_route(_:None=Depends(require_auth)):return {'pending':approvals.pending()}
@app.post('/api/approvals')
async def create_approval(payload:dict,_:None=Depends(require_auth)):return approvals.request(str(payload.get('action','')),str(payload.get('reason','')),payload.get('context') or {})
@app.post('/api/approvals/{approval_id}')
async def decide_approval(approval_id:str,payload:dict,_:None=Depends(require_auth)):
    item=approvals.decide(approval_id,bool(payload.get('approved')))
    if not item:raise HTTPException(404,'approval not found')
    audit_log.write('approval.decided',approval_id=approval_id,status=item['status'])
    if item['status']=='APPROVED' and payload.get('execute',True):
        ctx=item.get('context') or {};name=ctx.get('tool');args=ctx.get('args') or {};tool=registry.get(name)
        if not tool:raise HTTPException(400,'approved tool no longer exists')
        result=tool.fn(**args);result=await result if inspect.isawaitable(result) else result;result=result if isinstance(result,dict) else {'status':'SUCCESS','result':result};audit_log.write('approval.executed',approval_id=approval_id,tool=name,result=result);item['execution']=result
    return item
@app.get('/api/memory/lifecycle')
async def memory_lifecycle(_:None=Depends(require_auth)):return memory_service.snapshot()
@app.post('/api/memory/maintain')
async def memory_maintain(_:None=Depends(require_auth)):return {'decay':memory_service.decay(),'consolidation':memory_service.consolidate()}
@app.get('/api/sessions')
async def list_sessions(_:None=Depends(require_auth)):return {'sessions':conversations.list()}
@app.post('/api/sessions')
async def create_session(payload:dict,_:None=Depends(require_auth)):
    s=conversations.create(str(payload.get('title','New conversation')));agent.session=conversations.get_or_create(s['id']);return s
@app.get('/api/sessions/{session_id}')
async def get_session(session_id:str,_:None=Depends(require_auth)):return {'session':next((x for x in conversations.list() if x['id']==session_id),None),'messages':conversations.history(session_id,200)}
@app.post('/api/sessions/{session_id}/select')
async def select_session(session_id:str,_:None=Depends(require_auth)):
    s=conversations.get_or_create(session_id);agent.session=s;return s
@app.get('/api/integrations/accounts')
async def oauth_accounts(_:None=Depends(require_auth)):return {'accounts':accounts.list()}
@app.post('/api/integrations/accounts/{account_id}/disconnect')
async def oauth_disconnect(account_id:str,_:None=Depends(require_auth)):
    if not accounts.get(account_id):raise HTTPException(404,'account not found')
    return await agent.run_tool('oauth_revoke',{'account_id':account_id})
@app.get('/api/self/provenance')
async def self_provenance(_:None=Depends(require_auth)):return {'repository':str(PRODUCT_ROOT),'resource_root':str(resource_root()),'files':maintenance.inventory()}
@app.get('/api/process')
async def process_info(_:None=Depends(require_auth)):return {'pid':os.getpid(),'host':socket.gethostname(),'port':settings.port,'data_dir':str(DATA)}
@app.get('/api/voice/native')
async def native_voice_status(_:None=Depends(require_auth)):return {'running':native_voice.running}
@app.post('/api/voice/native/start')
async def native_voice_start(_:None=Depends(require_auth)):return await agent.run_tool('native_voice_start',{})
@app.post('/api/voice/native/stop')
async def native_voice_stop(_:None=Depends(require_auth)):return await agent.run_tool('native_voice_stop',{})
@app.get('/api/windows/tree')
async def windows_tree(window_title:str='',window_re:str='',_:None=Depends(require_auth)):return uia.control_tree(window_title,window_re)
@app.post('/api/windows/click')
async def windows_click(payload:dict,_:None=Depends(require_auth)):return await agent.run_tool('windows_click',payload)
@app.post('/api/windows/type')
async def windows_type(payload:dict,_:None=Depends(require_auth)):return await agent.run_tool('windows_type',payload)
@app.post('/api/windows/hotkey')
async def windows_hotkey(payload:dict,_:None=Depends(require_auth)):return await agent.run_tool('windows_hotkey',{'keys':payload.get('keys',[])})
@app.get('/api/federation/challenge')
async def federation_challenge(node_id:str,nonce:str,_:None=Depends(require_auth)):return {'node_id':node_id,'nonce':nonce,'signature':nodes.sign(node_id,nonce)}
@app.post('/api/federation/{node_id}/rotate')
async def federation_rotate(node_id:str,_:None=Depends(require_auth)):return await agent.run_tool('federation_rotate',{'node_id':node_id})
@app.post('/api/federation/{node_id}/revoke')
async def federation_revoke(node_id:str,_:None=Depends(require_auth)):return await agent.run_tool('federation_revoke',{'node_id':node_id})
__all__=['app']