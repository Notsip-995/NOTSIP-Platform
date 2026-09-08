from __future__ import annotations
import copy,importlib,uuid
from fastapi import HTTPException,Request
from fastapi.responses import JSONResponse

SECRET_NAMES={'api_key','event_hmac_secret','pairing_secret','llm_api_key','fallback_llm_api_key','stt_api_key','tts_api_key','email_password','oidc_client_secret','oauth_client_secret','node_shared_secret','brave_api_key','remote_compute_token','remote_sensing_token','home_adapter_token','biometric_adapter_token','flight_planning_token','business_admin_token'}
RUNTIME_UNSUPPORTED={'data_dir','database_url'}

def _redacted_config(mod):
    data=mod.config_store.load();safe={k:v for k,v in (data.get('settings') or {}).items() if k not in SECRET_NAMES and not any(x in k.lower() for x in ('password','secret','token','key'))};safe['database_url']='[configured]' if getattr(mod.settings,'database_url','') else '';return {'version':data.get('version',0),'settings':safe,'secret_configured':{k:bool(getattr(mod.settings,k,'')) or bool(mod.auth.secrets.get('NOTSIP_'+k.upper(),'')) for k in SECRET_NAMES}}

def _is_loopback(request):return (getattr(getattr(request,'client',None),'host','') or '') in {'127.0.0.1','::1','localhost'}

def attach(app):
    mod=importlib.import_module('notsip.app');app.router.routes=[r for r in app.router.routes if getattr(r,'path',None)!='/api/config']
    @app.get('/api/config')
    async def config_get_hardened(request:Request):
        await mod.require_auth(request);return _redacted_config(mod)
    @app.post('/api/config')
    async def config_set_hardened(payload:dict,request:Request):
        incoming=copy.deepcopy(payload);requested=dict(incoming.get('settings') or {})
        if not requested and not incoming.get('clear_secrets'):raise HTTPException(400,'settings are required')
        unknown=set(requested)-set(mod.settings.__class__.model_fields)
        if unknown:raise HTTPException(400,f'unsupported settings: {sorted(unknown)}')
        unsupported=sorted(set(requested)&RUNTIME_UNSUPPORTED)
        if unsupported:raise HTTPException(409,f"runtime cannot safely switch {unsupported}; configure them before startup and restart NOTSIP")
        clear=set(incoming.get('clear_secrets') or []);bad_clear=clear-SECRET_NAMES
        if bad_clear:raise HTTPException(400,f'unknown secret fields: {sorted(bad_clear)}')
        for key in clear:requested[key]=''
        # First-run bootstrap is intentionally separate from ordinary high-risk changes:
        # there is no authenticated actor yet, so local setup must establish the initial
        # security boundary atomically. settings.ensure() still rejects unsafe remote binds.
        bootstrap=not mod.config_store.path.exists()
        if bootstrap:
            if not _is_loopback(request):raise HTTPException(403,'initial NOTSIP setup is local-only')
            for key in list(requested):
                if key in SECRET_NAMES and not str(requested[key] or '').strip():requested.pop(key,None)
            try:
                result=mod._apply_config(requested)
            except RuntimeError as exc:raise HTTPException(400,str(exc))
        else:
            await mod.require_auth(request)
            sensitive=set(requested)&set(getattr(mod,'CONFIG_HIGH_RISK',set()))
            if sensitive or clear:
                pending_id=uuid.uuid4().hex
                # The pending record is encrypted; the approval record contains only the id
                # and key names, never raw credentials.
                mod.auth.secrets.set('config:pending:'+pending_id,requested)
                result=await mod.agent.run_tool('config_admin',{'pending_id':pending_id,'keys':sorted(sensitive or clear)})
                if result.get('status')=='FAILURE':mod.auth.secrets.delete('config:pending:'+pending_id)
            else:
                try:result=mod._apply_config(requested)
                except RuntimeError as exc:raise HTTPException(400,str(exc))
        result['bootstrap']=bootstrap
        response=JSONResponse(result)
        if getattr(mod.settings,'auth_mode','api_key')=='api_key' and getattr(mod.settings,'api_key',''):
            token=mod.auth.mint_session({'mode':'api_key','sub':'primary-user'});forwarded=(request.headers.get('x-forwarded-proto') or '').split(',')[0].strip().lower();secure=request.url.scheme=='https' or forwarded=='https';response.set_cookie('notsip_session',token,httponly=True,samesite='lax',secure=secure,max_age=mod.settings.session_ttl,path='/')
        return response
