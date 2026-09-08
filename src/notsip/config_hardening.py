from __future__ import annotations
import copy, importlib
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

SECRET_NAMES={'api_key','event_hmac_secret','pairing_secret','llm_api_key','fallback_llm_api_key','stt_api_key','tts_api_key','email_password','oidc_client_secret','oauth_client_secret','node_shared_secret','brave_api_key'}
RESTART_KEYS={'host','port','data_dir','database_url'}

def _redacted_config(mod):
    data=mod.config_store.load()
    safe={k:v for k,v in (data.get('settings') or {}).items() if k not in SECRET_NAMES and not any(x in k.lower() for x in ('password','secret','token','key'))}
    safe['database_url']='[configured]' if getattr(mod.settings,'database_url','') else ''
    return {'version':data.get('version',0),'settings':safe}

def attach(app):
    mod=importlib.import_module('notsip.app')
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None)!='/api/config']

    @app.get('/api/config')
    async def config_get_hardened(request:Request):
        await mod.require_auth(request)
        return _redacted_config(mod)

    @app.post('/api/config')
    async def config_set_hardened(payload:dict,request:Request):
        await mod.require_auth(request)
        incoming=copy.deepcopy(payload)
        settings_payload=dict(incoming.get('settings') or {})
        clear_secrets=set(incoming.get('clear_secrets') or [])
        unknown=clear_secrets-SECRET_NAMES
        if unknown:raise HTTPException(400,f'unknown secret fields: {sorted(unknown)}')
        for key in clear_secrets:
            mod.auth.secrets.delete('NOTSIP_'+key.upper());setattr(mod.settings,key,'')
        for key in SECRET_NAMES:
            if key in settings_payload and not str(settings_payload[key] or '').strip():
                settings_payload.pop(key,None)
        database_changed=False
        if 'database_url' in settings_payload:
            db_url=str(settings_payload.pop('database_url') or '').strip() or 'sqlite:///data/notsip.db'
            mod.settings.database_url=db_url
            database_changed=True
        incoming['settings']=settings_payload
        data=await mod.config_set(incoming,None)
        requested=set(settings_payload)
        if database_changed:requested.add('database_url')
        data['restart_required']=bool(RESTART_KEYS & requested)
        if data['restart_required']:
            data['restart_reason']='host, port, data directory, or database changes require a NOTSIP restart'
        response=JSONResponse(data)
        if mod.settings.auth_mode=='api_key' and mod.settings.api_key:
            token=mod.auth.mint_session({'mode':'api_key','sub':'primary-user'})
            response.set_cookie('notsip_session',token,httponly=True,samesite='lax',secure=False,max_age=mod.settings.session_ttl,path='/')
        return response
