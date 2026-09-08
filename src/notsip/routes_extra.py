from fastapi import Depends, HTTPException, Request
from .config import settings, SECRET_FIELDS
from .policy import Policy, Risk

def _public_settings():
    out={}
    for name in settings.__class__.model_fields:
        if name in SECRET_FIELDS:continue
        value=getattr(settings,name)
        if name=='data_dir':value=str(value)
        out[name]=value
    return {'version':2,'settings':out,'secret_configured':{name:bool(getattr(settings,name,None)) for name in SECRET_FIELDS}}

def attach(app,require_auth,web,emailc):
    @app.middleware('http')
    async def direct_capability_guard(request:Request,call_next):
        path=request.url.path
        cap='';risk=Risk.LOW;destructive=False
        if path.startswith('/api/windows/'):
            cap='CONTROL_COMPUTER';risk=Risk.MEDIUM
        elif path.startswith('/api/files/'):
            cap='WRITE_FILES';risk=Risk.HIGH if path.endswith('/delete') else Risk.MEDIUM;destructive=path.endswith('/delete')
        elif path in {'/api/voice/native/start','/api/voice/native/stop'}:
            cap='ACCESS_MICROPHONE';risk=Risk.MEDIUM
        if cap:
            d=Policy(settings.autonomy_level).decide(risk,destructive,capability=cap)
            if not d.allowed:
                return __import__('fastapi').responses.JSONResponse({'detail':'capability authorization required','capability':cap,'required_level':d.required_level,'reason':d.reason,'hint':'Use NOTSIP agent execution for an approval-gated action.'},status_code=403)
        return await call_next(request)

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
        from .runtime_prod import auth
        accounts=AccountStore(auth.secrets);oauth=OAuthService(accounts.secrets,accounts);item=accounts.get(account_id)
        if not item or item.get('provider')!=provider:raise HTTPException(404,'OAuth account not found')
        outcome=await oauth.revoke(provider,account_id)
        if outcome.get('status') in {'PROVIDER_REVOKED','PROVIDER_TOKEN_ALREADY_INVALID','ALREADY_REVOKED'}:
            accounts.disconnect(account_id);outcome['local_status']='DISCONNECTED'
        else:outcome['local_status']='CONNECTED'
        return outcome
