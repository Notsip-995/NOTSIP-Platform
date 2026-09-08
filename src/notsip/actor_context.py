from __future__ import annotations
from contextvars import ContextVar
from fastapi import Request

_current_actor: ContextVar[str]=ContextVar('notsip_actor',default='primary-user')


def current_actor() -> str:
    value=str(_current_actor.get() or 'primary-user').strip()
    return value or 'primary-user'


def set_actor(actor_id: str):
    value=str(actor_id or 'primary-user').strip() or 'primary-user'
    return _current_actor.set(value)


def reset_actor(token):
    _current_actor.reset(token)


def _safe_actor(claims: dict) -> str:
    provider=str(claims.get('iss') or claims.get('provider') or 'oidc').strip() or 'oidc'
    subject=str(claims.get('sub') or '').strip()
    if not subject: return 'primary-user'
    return f'{provider}:{subject}'

async def attach_actor_middleware(app, auth):
    @app.middleware('http')
    async def actor_context(request: Request, call_next):
        token=None
        try:
            actor='primary-user'
            cookie=request.cookies.get('notsip_session')
            if cookie and auth.validate_session(cookie):
                session=auth.sessions.get(cookie,{}) or {}
                claims=session.get('claims') or {}
                actor=_safe_actor(claims)
            elif request.headers.get('authorization','').startswith('Bearer '):
                bearer=request.headers.get('authorization','')[7:]
                if getattr(auth.settings,'api_key','') and bearer==auth.settings.api_key:actor='primary-user'
            token=set_actor(actor);request.state.notsip_actor=actor
            return await call_next(request)
        finally:
            if token is not None:reset_actor(token)
    return app
