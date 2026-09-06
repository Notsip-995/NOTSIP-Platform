from fastapi import Depends, HTTPException, Request
from .config import settings, SECRET_FIELDS

def _public_settings():
    out={}
    for name in settings.__class__.model_fields:
        if name in SECRET_FIELDS:continue
        value=getattr(settings,name)
        if name=='data_dir': value=str(value)
        out[name]=value
    return {'version':2,'settings':out,'secret_configured':{name:bool(getattr(settings,name,None)) for name in SECRET_FIELDS}}

def attach(app,require_auth,web,emailc):
    @app.get('/api/search')
    async def search(q:str,count:int=5,_:None=Depends(require_auth)):
        if not web.enabled:raise HTTPException(503,'Web search not configured')
        return {'results':await web.search(q,max(1,min(int(count),20)))}
    @app.get('/api/email/status')
    async def email_status(_:None=Depends(require_auth)):
        return {'configured':emailc.enabled,'smtp':bool(settings.smtp_host),'imap':bool(settings.imap_host),'username_configured':bool(settings.email_username)}
    @app.get('/api/config/public')
    async def config_public(request:Request):
        client=request.client.host if request.client else ''
        if client not in {'127.0.0.1','::1'}:raise HTTPException(403,'local setup endpoint only')
        return _public_settings()
