from __future__ import annotations
import importlib, secrets, time
from collections import defaultdict, deque
from fastapi import Request
from fastapi.responses import JSONResponse

class LoginRateLimiter:
    def __init__(self, limit:int=10, window:float=60.0):
        self.limit=limit; self.window=window; self.attempts=defaultdict(deque)
    def _prune(self,ip):
        now=time.time();q=self.attempts[ip]
        while q and now-q[0]>=self.window:q.popleft()
        return q
    def blocked(self,ip):return len(self._prune(ip))>=self.limit
    def record_failure(self,ip):self._prune(ip).append(time.time())

def attach(app):
    mod=importlib.import_module('notsip.app')
    limiter=LoginRateLimiter()
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None)!='/api/login']

    @app.post('/api/login')
    async def api_login(payload:dict):
        if mod.settings.auth_mode!='api_key':
            return JSONResponse({'detail':'API-key login is disabled while OIDC authentication is active'},status_code=403)
        if not mod.settings.api_key:
            return JSONResponse({'detail':'API key authentication is disabled; local access is open'},status_code=503)
        supplied=str(payload.get('api_key',''))
        if not secrets.compare_digest(supplied,mod.settings.api_key):
            return JSONResponse({'detail':'invalid API key'},status_code=401)
        token=mod.auth.mint_session({'mode':'api_key','sub':'primary-user'})
        r=JSONResponse({'authenticated':True})
        r.set_cookie('notsip_session',token,httponly=True,samesite='lax',secure=False,max_age=mod.settings.session_ttl,path='/')
        return r

    @app.middleware('http')
    async def hardened_security(request:Request,call_next):
        # A valid OIDC/API session cookie is authoritative for browser auth.
        # The legacy middleware may add an API-key bearer header from the cookie;
        # strip that synthetic header in OIDC mode so it cannot trip the bearer
        # rejection below. Real bearer API-key authentication remains rejected.
        if mod.settings.auth_mode=='oidc':
            cookie=request.cookies.get('notsip_session')
            if cookie and mod.auth.validate_session(cookie):
                headers=[(k,v) for (k,v) in request.scope.get('headers',[]) if k.lower()!=b'authorization']
                request.scope['headers']=headers
        if mod.settings.auth_mode=='oidc' and request.headers.get('authorization','').startswith('Bearer '):
            bearer=request.headers.get('authorization','')[7:]
            if mod.settings.api_key and secrets.compare_digest(bearer,mod.settings.api_key):
                return JSONResponse({'detail':'OIDC authentication required'},status_code=401)
        if request.url.path=='/api/login' and request.method=='POST':
            ip=request.client.host if request.client else 'unknown'
            if limiter.blocked(ip):
                return JSONResponse({'detail':'too many login attempts; try again later'},status_code=429)
            response=await call_next(request)
            if response.status_code in (401,403):limiter.record_failure(ip)
        else:
            response=await call_next(request)
        response.headers.setdefault('X-Content-Type-Options','nosniff')
        response.headers.setdefault('X-Frame-Options','DENY')
        response.headers.setdefault('Referrer-Policy','no-referrer')
        return response
