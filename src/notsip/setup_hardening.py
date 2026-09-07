from __future__ import annotations
import importlib, copy
from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

SECRET_NAMES={'api_key','event_hmac_secret','pairing_secret','llm_api_key','fallback_llm_api_key','stt_api_key','tts_api_key','email_password','oidc_client_secret','oauth_client_secret','node_shared_secret','brave_api_key'}
RESTART_KEYS={'host','port','data_dir','database_url'}

def _public_state(mod):
    data=mod.config_store.load();saved=dict(data.get('settings') or {})
    safe={k:v for k,v in saved.items() if k not in SECRET_NAMES and not any(x in k.lower() for x in ('password','secret'))}
    if 'database_url' in safe:
        from urllib.parse import urlsplit,urlunsplit
        try:
            p=urlsplit(str(safe['database_url']))
            if p.username or p.password:
                host=p.hostname or '';port=f':{p.port}' if p.port else ''
                safe['database_url']=urlunsplit((p.scheme,f'{p.username or ""}:***@{host}{port}' if p.username else f'{host}{port}',p.path,p.query,p.fragment))
        except Exception:safe['database_url']='[configured]'
    return {'version':data.get('version',0),'settings':safe,'secret_configured':{k:bool(getattr(mod.settings,k,'')) or bool(mod.auth.secrets.get('NOTSIP_'+k.upper(),'')) for k in SECRET_NAMES}}

async def _require_after_setup(mod,request):
    if mod.config_store.path.exists():await mod.require_auth(request)

def attach(app):
    mod=importlib.import_module('notsip.app')
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in {'/api/config','/api/config/public','/setup'}]

    @app.get('/setup',include_in_schema=False)
    async def setup_page(request:Request):
        await _require_after_setup(mod,request)
        p=mod.resource_root()/'setup.html'
        if not p.exists():raise HTTPException(404,'setup UI missing')
        return FileResponse(p)

    @app.get('/api/config/public')
    async def config_public(request:Request):
        await _require_after_setup(mod,request);return _public_state(mod)

    @app.get('/api/config')
    async def config_get_public(request:Request):
        await _require_after_setup(mod,request)
        try:return await mod.config_get(None)
        except Exception as exc:raise HTTPException(500,str(exc))

    @app.post('/api/config')
    async def config_set_with_session(payload:dict,request:Request):
        await _require_after_setup(mod,request)
        incoming=copy.deepcopy(payload);settings_payload=dict(incoming.get('settings') or {})
        clear_secrets=set(incoming.get('clear_secrets') or [])
        unknown=clear_secrets-SECRET_NAMES
        if unknown:raise HTTPException(400,f'unknown secret fields: {sorted(unknown)}')
        for key in clear_secrets:
            mod.auth.secrets.delete('NOTSIP_'+key.upper());setattr(mod.settings,key,'')
        for key in SECRET_NAMES:
            if key in settings_payload and not str(settings_payload[key] or '').strip():
                settings_payload.pop(key,None)
        incoming['settings']=settings_payload
        data=await mod.config_set(incoming,None)
        data['restart_required']=any(k in RESTART_KEYS for k in settings_payload)
        if data['restart_required']:
            data['restart_reason']='host, port, data directory, or database changes require a NOTSIP restart'
        response=JSONResponse(data)
        if mod.settings.auth_mode=='api_key' and mod.settings.api_key:
            token=mod.auth.mint_session({'mode':'api_key','sub':'primary-user'});response.set_cookie('notsip_session',token,httponly=True,samesite='lax',secure=False,max_age=mod.settings.session_ttl,path='/')
        return response
