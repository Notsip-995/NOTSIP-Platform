from __future__ import annotations
import importlib
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse

RESTART_KEYS={'host','port','data_dir','database_url'}

def attach(app):
    mod=importlib.import_module('notsip.app')
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None)!='/api/config']
    @app.post('/api/config')
    async def config_set_hardened(payload:dict,request:Request):
        await mod.require_auth(request)
        data=await mod.config_set(payload,None)
        requested=set((payload.get('settings') or {}).keys())
        data['restart_required']=bool(RESTART_KEYS & requested)
        if data['restart_required']:
            data['restart_reason']='host, port, data directory, or database changes require a NOTSIP restart'
        response=JSONResponse(data)
        if mod.settings.auth_mode=='api_key' and mod.settings.api_key:
            token=mod.auth.mint_session({'mode':'api_key','sub':'primary-user'})
            response.set_cookie('notsip_session',token,httponly=True,samesite='lax',secure=False,max_age=mod.settings.session_ttl,path='/')
        return response
