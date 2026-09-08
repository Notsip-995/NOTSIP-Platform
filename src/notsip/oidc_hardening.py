from __future__ import annotations
import secrets,time
from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from .security import pkce_pair


def attach(app,auth,accounts,settings):
    paths={'/api/oauth/login','/api/oauth/callback'}
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in paths]

    @app.get('/api/oauth/login')
    async def oauth_login_hardened():
        if not auth.oidc.configured:raise HTTPException(503,'OIDC is not configured')
        verifier,challenge=pkce_pair();state=secrets.token_urlsafe(32);nonce=secrets.token_urlsafe(24);csrf=secrets.token_urlsafe(32)
        auth.sessions['oidc:'+state]={'verifier':verifier,'nonce':nonce,'csrf':csrf,'expires':time.time()+600}
        response=RedirectResponse(await auth.oidc.authorize_url(state,challenge,nonce))
        response.set_cookie('notsip_oidc_csrf',csrf,httponly=True,samesite='lax',secure=settings.oidc_redirect_uri.startswith('https://'),max_age=600,path='/api/oauth')
        return response

    @app.get('/api/oauth/callback')
    async def oauth_callback_hardened(code:str,state:str,notsip_oidc_csrf:str|None=None):
        pending=auth.sessions.pop('oidc:'+state,None)
        if not pending or float(pending.get('expires',0))<time.time():raise HTTPException(400,'invalid or expired OIDC state')
        if not secrets.compare_digest(str(pending.get('csrf','')),str(notsip_oidc_csrf or '')):raise HTTPException(400,'OIDC browser state validation failed')
        tokens=await auth.oidc.exchange(code,pending['verifier']);claims={}
        if tokens.get('id_token'):claims=await auth.oidc.validate_id_token(tokens['id_token'],pending['nonce'])
        elif tokens.get('access_token'):claims=await auth.oidc.userinfo(tokens['access_token'])
        subject=str(claims.get('sub') or '').strip()
        if not subject:raise HTTPException(400,'OIDC identity subject missing')
        account=accounts.upsert(settings.oidc_provider,subject,claims.get('email',''),auth.oidc.scopes,{'expires_at':tokens.get('expires_at'),'token_type':tokens.get('token_type')});accounts.save_tokens(account['id'],tokens)
        session=auth.mint_session({'claims':claims,'account_id':account['id']})
        response=RedirectResponse('/')
        response.set_cookie('notsip_session',session,httponly=True,secure=settings.oidc_redirect_uri.startswith('https://'),samesite='lax',max_age=settings.session_ttl,path='/')
        response.delete_cookie('notsip_oidc_csrf',path='/api/oauth')
        return response
