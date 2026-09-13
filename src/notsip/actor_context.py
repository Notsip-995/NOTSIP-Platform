from __future__ import annotations
from contextvars import ContextVar
from fastapi import Request
import secrets

_current_actor: ContextVar[str|None]=ContextVar('notsip_actor',default=None)
_actor_explicit: ContextVar[bool]=ContextVar('notsip_actor_explicit',default=False)

def current_actor()->str:
    value=str(_current_actor.get() or 'primary-user').strip()
    return value or 'primary-user'

def actor_is_explicit()->bool:
    """Return True when an actor was bound with set_actor (not the implicit default)."""
    return bool(_actor_explicit.get())

def set_actor(actor_id:str):
    token=_current_actor.set(str(actor_id or 'primary-user').strip() or 'primary-user')
    previous_explicit=_actor_explicit.get()
    _actor_explicit.set(True)
    return (token, previous_explicit)

def reset_actor(token):
    _current_actor.reset(token[0])
    _actor_explicit.set(token[1])

def _safe_actor(claims:dict)->str:
    mode=str(claims.get('mode') or '').strip()
    subject=str(claims.get('sub') or '').strip()
    # The primary administrative actor is identified by the API-key login/setup
    # session, not by an OIDC subject. Treating mode='api_key' sessions as
    # f'{issuer}:{sub}' made config_set return 403 on every save after the first.
    if mode == 'api_key':
        return subject or 'primary-user'
    if not subject:
        return 'primary-user'
    issuer=str(claims.get('iss') or claims.get('provider') or '').strip()
    if not issuer:
        return subject or 'primary-user'
    return f'{issuer}:{subject}'

def attach_actor_middleware(app,auth):
    @app.middleware('http')
    async def actor_context(request:Request,call_next):
        token=None
        try:
            actor='primary-user';cookie=request.cookies.get('notsip_session')
            if cookie and auth.validate_session(cookie):
                session=auth.sessions.get(cookie,{}) or {};actor=_safe_actor(session.get('claims') or {})
            elif auth.mode!='oidc' and request.headers.get('authorization','').startswith('Bearer '):
                bearer=request.headers.get('authorization','')[7:]
                configured=str(getattr(auth.settings,'api_key','') or '')
                if configured and secrets.compare_digest(bearer,configured):actor='primary-user'
            request.state.notsip_actor=actor;token=set_actor(actor);return await call_next(request)
        finally:
            if token is not None:reset_actor(token)
