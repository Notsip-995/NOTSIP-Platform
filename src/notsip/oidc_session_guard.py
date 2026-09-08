from fastapi import Request


def attach(app, auth):
    """Prevent the legacy session bridge from converting OIDC browser sessions to the primary API key."""
    @app.middleware('http')
    async def oidc_session_guard(request: Request, call_next):
        if auth.mode == 'oidc' and request.cookies.get('notsip_session') and auth.validate_session(request.cookies['notsip_session']):
            headers = list(request.scope.get('headers', []))
            has_auth = any(k.lower() == b'authorization' for k, _ in headers)
            if not has_auth:
                headers.append((b'authorization', b'Bearer oidc-session'))
                request.scope['headers'] = headers
        return await call_next(request)
