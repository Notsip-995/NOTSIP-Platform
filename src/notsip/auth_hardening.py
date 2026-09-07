from __future__ import annotations
import time
from fastapi import Request
from fastapi.responses import JSONResponse

_ATTEMPTS: dict[str, list[float]] = {}
_WINDOW = 60.0
_LIMIT = 10

def attach(app):
    @app.middleware('http')
    async def login_rate_limit(request: Request, call_next):
        if request.url.path == '/api/login' and request.method == 'POST':
            ip = request.client.host if request.client else 'unknown'
            now = time.time()
            recent = [t for t in _ATTEMPTS.get(ip, []) if now - t < _WINDOW]
            if len(recent) >= _LIMIT:
                return JSONResponse({'detail': 'too many login attempts; retry later'}, status_code=429)
            recent.append(now)
            _ATTEMPTS[ip] = recent
        return await call_next(request)
