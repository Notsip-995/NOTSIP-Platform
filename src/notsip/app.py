from __future__ import annotations
import json, time, urllib.parse, uuid
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from .runtime_prod import app, media, settings, store, nodes, recovery, intellect, events, web, emailc, require_auth, auth, provider, pairing
from .streaming import attach as attach_streaming
from .background import attach as attach_background
from .routes_extra import attach as attach_extra
from .product_layer import resource_root, repo_root, ConfigStore, AuditLog, BackupManager, ApprovalStore, Diagnostics, Maintenance, CapabilityProbe
attach_streaming(app, media, settings, settings.api_key)
attach_background(app, store, nodes, recovery, intellect, events, settings.perception_interval)
attach_extra(app, require_auth, web, emailc)
PRODUCT_ROOT=repo_root(); DATA=Path(settings.data_dir).resolve(); config_store=ConfigStore(DATA); audit_log=AuditLog(DATA); backups=BackupManager(DATA); approvals=ApprovalStore(DATA); diagnostics=Diagnostics(DATA,settings,store,provider,web,emailc); maintenance=Maintenance(PRODUCT_ROOT); probes=CapabilityProbe(settings,store,provider,web,emailc)

app.router.routes=[r for r in app.router.routes if not (getattr(r,'path',None)=='/' and 'GET' in getattr(r,'methods',set()))]
@app.get('/',include_in_schema=False)
async def product_root():
    ui=resource_root()/'ui.html'
    if ui.exists():return FileResponse(ui)
    return JSONResponse({'name':'NOTSIP','version':'0.9.0','status':'online','error':'UI resource missing'})
@app.get('/setup',include_in_schema=False)
async def setup_page():
    p=resource_root()/'setup.html'
    if not p.exists():raise HTTPException(404,'setup UI missing')
    return FileResponse(p)

_session_path=DATA/'runtime'/'sessions.json'
def _sessions():
    try:return json.loads(_session_path.read_text())
    except Exception:return {}
def _save_sessions(d):
    _session_path.parent.mkdir(parents=True,exist_ok=True);tmp=_session_path.with_suffix('.tmp');tmp.write_text(json.dumps(d,sort_keys=True));tmp.replace(_session_path)
_old_mint=auth.mint_session
def _mint_persistent(claims):
    token=_old_mint(claims);d=_sessions();d[token]={'claims':claims,'expires':time.time()+settings.session_ttl};_save_sessions(d);return token
def _validate_persistent(token):
    d=_sessions();s=d.get(token)
    if not s or s.get('expires',0)<=time.time():
        if token in d:d.pop(token);_save_sessions(d)
        return False
    auth.sessions[token]=s
    return True
auth.mint_session=_mint_persistent
auth.validate_session=_validate_persistent
_pair_attempts={}
def _rate_limited(ip:str,window=60,limit=15):
    now=time.time();recent=[t for t in _pair_attempts.get(ip,[]) if now-t<window];_pair_attempts[ip]=recent
    if len(recent)>=limit:return True
    recent.append(now);return False

@app.middleware('http')
async def production_security(request:Request,call_next):
    rid=request.headers.get('X-Request-ID') or uuid.uuid4().hex;request.state.request_id=rid
    if request.url.path=='/api/devices/result':
        device_id=request.headers.get('X-NOTSIP-Device-ID','');device_token=request.headers.get('X-NOTSIP-Device-Token','')
        if not device_id or not device_token or not store.device_token_valid(device_id,device_token):
            return JSONResponse({'detail':'device authentication required'},status_code=401,headers={'X-Request-ID':rid})
    if request.url.path=='/api/pair/consume' and _rate_limited(request.client.host if request.client else 'unknown'):
        return JSONResponse({'detail':'pairing rate limit exceeded'},status_code=429,headers={'X-Request-ID':rid})
    try:response=await call_next(request)
    except Exception as exc:audit_log.write('request.error',request_id=rid,path=request.url.path,error=str(exc));raise
    response.headers['X-Request-ID']=rid;audit_log.write('request',request_id=rid,method=request.method,path=request.url.path,status=response.status_code);return response

@app.get('/api/capabilities')
async def capabilities(_:None=Depends(require_auth)):return {'configured':probes.snapshot(),'diagnostics':diagnostics.run()}
@app.get('/api/diagnostics')
async def diagnostics_route(_:None=Depends(require_auth)):return diagnostics.run()
@app.get('/api/audit/log')
async def audit_log_route(_:None=Depends(require_auth)):return {'events':audit_log.tail()}
@app.get('/api/config')
async def config_get(_:None=Depends(require_auth)):
    data=config_store.load();data['settings']={k:v for k,v in data.get('settings',{}).items() if not any(x in k.lower() for x in ('key','password','secret'))};return data
@app.post('/api/config')
async def config_set(payload:dict,_:None=Depends(require_auth)):
    requested=dict(payload.get('settings') or {});allowed={k for k in settings.__class__.model_fields.keys() if not any(x in k.lower() for x in ('api_key','password','secret','client_secret'))}
    secret_names={'api_key','event_hmac_secret','pairing_secret','llm_api_key','fallback_llm_api_key','stt_api_key','tts_api_key','email_password','oidc_client_secret','oauth_client_secret','node_shared_secret'}
    for k,v in requested.items():
        if k in allowed:setattr(settings,k,v)
        elif k in secret_names:auth.secrets.set('NOTSIP_'+k.upper(),str(v));setattr(settings,k,str(v))
    config_store.save({k:getattr(settings,k) for k in allowed});audit_log.write('config.updated',keys=sorted(requested));return {'status':'SUCCESS','version':2,'changed':sorted(requested)}
@app.post('/api/diagnostics/test-config')
async def test_config(_:None=Depends(require_auth)):return diagnostics.run()
@app.post('/api/backups')
async def create_backup(_:None=Depends(require_auth)):return backups.create()
@app.get('/api/backups')
async def list_backups(_:None=Depends(require_auth)):return {'backups':backups.list()}
@app.get('/api/backups/{name}/verify')
async def verify_backup(name:str,_:None=Depends(require_auth)):return backups.verify(name)
@app.get('/api/approvals')
async def approvals_route(_:None=Depends(require_auth)):return {'pending':approvals.pending()}
@app.post('/api/approvals/{approval_id}')
async def decide_approval(approval_id:str,payload:dict,_:None=Depends(require_auth)):
    item=approvals.decide(approval_id,bool(payload.get('approved')))
    if not item:raise HTTPException(404,'approval not found')
    audit_log.write('approval.decided',approval_id=approval_id,status=item['status']);return item
@app.get('/api/self/provenance')
async def self_provenance(_:None=Depends(require_auth)):return {'repository':str(PRODUCT_ROOT),'resource_root':str(resource_root()),'files':maintenance.inventory()}
@app.get('/api/process')
async def process_info(_:None=Depends(require_auth)):return {'pid':__import__('os').getpid(),'host':__import__('socket').gethostname(),'port':settings.port,'data_dir':str(DATA)}
__all__=['app']
