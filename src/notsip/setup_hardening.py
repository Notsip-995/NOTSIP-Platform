from __future__ import annotations
import importlib
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

def attach(app):
    mod=importlib.import_module('notsip.app')
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in {'/api/config'}]

    @app.get('/api/config')
    async def config_get_public():
        try:return await mod.config_get(None)
        except Exception as exc:raise HTTPException(500,str(exc))

    @app.post('/api/config')
    async def config_set_with_session(payload:dict,request:Request):
        try:data=await mod.config_set(payload,None)
        except Exception as exc:
            raise
        response=JSONResponse(data)
        if mod.settings.auth_mode=='api_key' and mod.settings.api_key:
            token=mod.auth.mint_session({'mode':'api_key','sub':'primary-user'})
            response.set_cookie('notsip_session',token,httponly=True,samesite='lax',secure=False,max_age=mod.settings.session_ttl,path='/')
        return response
