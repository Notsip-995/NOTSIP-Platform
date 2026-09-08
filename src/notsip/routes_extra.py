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
    @app.post('/api/oauth/{provider}/revoke/{account_id}')
    async def oauth_revoke(provider:str,account_id:str,_:None=Depends(require_auth)):
        from .account_store import AccountStore
        from .oauth_services import OAuthService
        accounts=AccountStore(__import__('notsip.runtime_prod',fromlist=['auth']).auth.secrets)
        oauth=OAuthService(accounts.secrets,accounts)
        item=accounts.get(account_id)
        if not item or item.get('provider')!=provider:raise HTTPException(404,'OAuth account not found')
        outcome=await oauth.revoke(provider,account_id)
        if outcome.get('status') in {'PROVIDER_REVOKED','PROVIDER_TOKEN_ALREADY_INVALID','ALREADY_REVOKED'}:
            accounts.disconnect(account_id);outcome['local_status']='DISCONNECTED'
        else:
            outcome['local_status']='CONNECTED'
        return outcome
