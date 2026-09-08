from __future__ import annotations
import secrets,time
from fastapi import Cookie,HTTPException
from fastapi.responses import RedirectResponse
from .security import pkce_pair,_require_public_https

async def _safe_validate_id_token(provider,id_token,nonce=''):
    import httpx,jwt
    metadata=provider.metadata or await provider.discover();jwks_uri=str(metadata.get('jwks_uri') or '').strip()
    if not jwks_uri:raise ValueError('OIDC metadata missing jwks_uri')
    _require_public_https(jwks_uri)
    async with httpx.AsyncClient(timeout=20,follow_redirects=False,trust_env=False) as client:
        response=await client.get(jwks_uri,headers={'Accept':'application/json'})
    if response.is_redirect or response.is_permanent_redirect:raise ValueError('OIDC JWKS redirect rejected')
    response.raise_for_status()
    if len(response.content)>5*1024*1024:raise ValueError('OIDC JWKS response exceeded safety limit')
    jwks=response.json();header=jwt.get_unverified_header(id_token);alg=str(header.get('alg') or '');kid=header.get('kid');advertised=metadata.get('id_token_signing_alg_values_supported') or ['RS256']
    if not alg or alg not in {str(x) for x in advertised}:raise ValueError('OIDC ID token signing algorithm is not allowed by provider metadata')
    keyset=jwt.PyJWKSet.from_dict(jwks);key=None
    for candidate in keyset.keys:
        if kid is None or getattr(candidate,'key_id',None)==kid:key=candidate;break
    if key is None:raise ValueError('OIDC JWKS does not contain the token key id')
    claims=jwt.decode(id_token,key.key,algorithms=[alg],audience=provider.client_id,options={'require':['exp','iat','iss','sub']})
    expected=str(metadata.get('issuer') or provider.issuer).rstrip('/');iss=str(claims.get('iss') or '')
    if '{tenantid}' in expected:expected=expected.replace('{tenantid}',str(claims.get('tid') or ''))
    if iss!=expected:raise ValueError('OIDC issuer validation failed')
    if nonce and claims.get('nonce')!=nonce:raise ValueError('OIDC nonce validation failed')
    return claims

def attach(app,auth,accounts,settings):
    paths={'/api/oauth/login','/api/oauth/callback'};app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in paths];auth.oidc.validate_id_token=_safe_validate_id_token.__get__(auth.oidc,type(auth.oidc))
    @app.get('/api/oauth/login')
    async def oauth_login_hardened():
        if not auth.oidc.configured:raise HTTPException(503,'OIDC is not configured')
        verifier,challenge=pkce_pair();state=secrets.token_urlsafe(32);nonce=secrets.token_urlsafe(24);csrf=secrets.token_urlsafe(32)
        auth.sessions['oidc:'+state]={'verifier':verifier,'nonce':nonce,'csrf':csrf,'expires':time.time()+600}
        response=RedirectResponse(await auth.oidc.authorize_url(state,challenge,nonce));response.set_cookie('notsip_oidc_csrf',csrf,httponly=True,samesite='lax',secure=settings.oidc_redirect_uri.startswith('https://'),max_age=600,path='/api/oauth');return response
    @app.get('/api/oauth/callback')
    async def oauth_callback_hardened(code:str,state:str,notsip_oidc_csrf:str|None=Cookie(default=None)):
        key='oidc:'+state;pending=auth.sessions.get(key)
        if not pending or float(pending.get('expires',0))<time.time():raise HTTPException(400,'invalid or expired OIDC state')
        if not secrets.compare_digest(str(pending.get('csrf','')),str(notsip_oidc_csrf or '')):raise HTTPException(400,'OIDC browser state validation failed')
        tokens=await auth.oidc.exchange(code,pending['verifier']);claims={}
        if tokens.get('id_token'):claims=await auth.oidc.validate_id_token(tokens['id_token'],pending['nonce'])
        elif tokens.get('access_token'):claims=await auth.oidc.userinfo(tokens['access_token'])
        subject=str(claims.get('sub') or '').strip()
        if not subject:raise HTTPException(400,'OIDC identity subject missing')
        actor=__import__('notsip.actor_context',fromlist=['current_actor']).current_actor();account=accounts.upsert(settings.oidc_provider,subject,claims.get('email',''),auth.oidc.scopes,{'expires_at':tokens.get('expires_at'),'token_type':tokens.get('token_type')},owner=actor);accounts.save_tokens(account['id'],tokens,owner=actor);auth.sessions.pop(key,None)
        session=auth.mint_session({'claims':claims,'account_id':account['id']});response=RedirectResponse('/');response.set_cookie('notsip_session',session,httponly=True,secure=settings.oidc_redirect_uri.startswith('https://'),samesite='lax',max_age=settings.session_ttl,path='/');response.delete_cookie('notsip_oidc_csrf',path='/api/oauth');return response
