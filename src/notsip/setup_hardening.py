from __future__ import annotations
import importlib
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

SECRET_NAMES={'api_key','event_hmac_secret','pairing_secret','llm_api_key','fallback_llm_api_key','stt_api_key','tts_api_key','email_password','oidc_client_secret','oauth_client_secret','node_shared_secret','brave_api_key'}

def _public_state(mod):
    data=mod.config_store.load()
    saved=dict(data.get('settings') or {})
    safe={k:v for k,v in saved.items() if k not in SECRET_NAMES and not any(x in k.lower() for x in ('password','secret'))}
    return {'version':data.get('version',0),'settings':safe,'secret_configured':{k:bool(getattr(mod.settings,k,'')) or bool(mod.auth.secrets.get('NOTSIP_'+k.upper(),'')) for k in SECRET_NAMES}}

def attach(app):
    mod=importlib.import_module('notsip.app')
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in {'/api/config','/api/config/public'}]

    @app.get('/api/config/public')
    async def config_public():return _public_state(mod)

    @app.get('/api/config')
    async def config_get_public():
        try:return await mod.config_get(None)
        except Exception as exc:raise HTTPException(500,str(exc))

    @app.post('/api/config')
    async def config_set_with_session(payload:dict,request:Request):
        data=await mod.config_set(payload,None)
        response=JSONResponse(data)
        if mod.settings.auth_mode=='api_key' and mod.settings.api_key:
            token=mod.auth.mint_session({'mode':'api_key','sub':'primary-user'})
            response.set_cookie('notsip_session',token,httponly=True,samesite='lax',secure=False,max_age=mod.settings.session_ttl,path='/')
        return response
