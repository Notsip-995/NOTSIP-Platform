from __future__ import annotations
import importlib, copy
from urllib.parse import urlsplit, urlunsplit
from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

SECRET_NAMES={'api_key','event_hmac_secret','pairing_secret','llm_api_key','fallback_llm_api_key','stt_api_key','tts_api_key','email_password','oidc_client_secret','oauth_client_secret','node_shared_secret','brave_api_key','database_url'}
RESTART_KEYS={'host','port','data_dir','database_url'}

def _redact_database_url(value):
    try:
        p=urlsplit(str(value))
        if not p.scheme:return str(value)
        if p.username or p.password:
            host=p.hostname or '';port=f':{p.port}' if p.port else '';user=f'{p.username}:***@' if p.username else ''
            return urlunsplit((p.scheme,f'{user}{host}{port}',p.path,p.query,p.fragment))
        return str(value)
    except Exception:return '[configured]'

def _public_state(mod):
    data=mod.config_store.load();saved=dict(data.get('settings') or {})
    safe={k:v for k,v in saved.items() if k not in SECRET_NAMES and not any(x in k.lower() for x in ('password','secret'))}
    safe['database_url']=_redact_database_url(getattr(mod.settings,'database_url',''))
    return {'version':data.get('version',0),'settings':safe,'secret_configured':{k:bool(getattr(mod.settings,k,'')) or bool(mod.auth.secrets.get('NOTSIP_'+k.upper(),'')) for k in SECRET_NAMES}}

def _local_oidc_recovery(mod,request):
    host=getattr(getattr(request,'client',None),'host','') or ''
    return host in {'127.0.0.1','::1'} and mod.settings.auth_mode=='oidc' and not mod.auth.oidc.configured

async def _require_after_setup(mod,request):
    if mod.config_store.path.exists() and not _local_oidc_recovery(mod,request):await mod.require_auth(request)

def attach(app):
    mod=importlib.import_module('notsip.app')
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in {'/api/config','/api/config/public','/setup'}]
    @app.get('/setup',include_in_schema=False)
    async def setup_page(request:Request):
        await _require_after_setup(mod,request);p=mod.resource_root()/'setup.html'
        if not p.exists():raise HTTPException(404,'setup UI missing')
        return FileResponse(p)
    @app.get('/api/config/public')
    async def config_public(request:Request):
        await _require_after_setup(mod,request);return _public_state(mod)
    @app.get('/api/config')
    async def config_get_public(request:Request):
        await _require_after_setup(mod,request)
        try:
            data=await mod.config_get(None)
            settings_data=data.get('settings',{}) if isinstance(data,dict) else {}
            if isinstance(settings_data,dict) and 'database_url' in settings_data:settings_data['database_url']=_redact_database_url(settings_data['database_url'])
            return data
        except Exception as exc:raise HTTPException(500,str(exc))
    @app.post('/api/config')
    async def config_set_with_session(payload:dict,request:Request):
        await _require_after_setup(mod,request)
        incoming=copy.deepcopy(payload);settings_payload=dict(incoming.get('settings') or {});clear_secrets=set(incoming.get('clear_secrets') or [])
        unknown=clear_secrets-SECRET_NAMES
        if unknown:raise HTTPException(400,f'unknown secret fields: {sorted(unknown)}')
        for key in clear_secrets:mod.auth.secrets.delete('NOTSIP_'+key.upper());setattr(mod.settings,key,'')
        database_url=settings_payload.pop('database_url',None)
        if database_url is not None:
            database_url=str(database_url).strip()
            if not database_url:database_url='sqlite:///data/notsip.db'
            mod.auth.secrets.set('NOTSIP_DATABASE_URL',database_url);mod.settings.database_url=database_url
        for key in SECRET_NAMES:
            if key in settings_payload and not str(settings_payload[key] or '').strip():settings_payload.pop(key,None)
        incoming['settings']=settings_payload;data=await mod.config_set(incoming,None);data['restart_required']=any(k in RESTART_KEYS for k in (set(settings_payload)|({'database_url'} if database_url is not None else set())))
        if data['restart_required']:data['restart_reason']='host, port, data directory, or database changes require a NOTSIP restart'
        response=JSONResponse(data)
        if mod.settings.auth_mode=='api_key' and mod.settings.api_key:
            token=mod.auth.mint_session({'mode':'api_key','sub':'primary-user'});response.set_cookie('notsip_session',token,httponly=True,samesite='lax',secure=False,max_age=mod.settings.session_ttl,path='/')
        return response
