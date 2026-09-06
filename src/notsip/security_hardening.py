from __future__ import annotations
import time
from collections import defaultdict, deque
from fastapi import Request
from fastapi.responses import JSONResponse

class LoginRateLimiter:
    def __init__(self, limit:int=10, window:float=60.0):
        self.limit=limit
        self.window=window
        self.attempts=defaultdict(deque)
    def blocked(self,ip:str)->bool:
        now=time.time();q=self.attempts[ip]
        while q and now-q[0]>=self.window:q.popleft()
        if len(q)>=self.limit:return True
        q.append(now);return False

def attach(app):
    limiter=LoginRateLimiter()
    @app.middleware('http')
    async def hardened_security(request:Request,call_next):
        if request.url.path=='/api/login' and request.method=='POST':
            ip=request.client.host if request.client else 'unknown'
            if limiter.blocked(ip):
                return JSONResponse({'detail':'too many login attempts; try again later'},status_code=429)
        response=await call_next(request)
        response.headers.setdefault('X-Content-Type-Options','nosniff')
        response.headers.setdefault('X-Frame-Options','DENY')
        response.headers.setdefault('Referrer-Policy','no-referrer')
        return response
