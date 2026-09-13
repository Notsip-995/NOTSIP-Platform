from __future__ import annotations

REDIRECT_STATUSES = {300, 301, 302, 303, 307, 308}
PERMANENT_REDIRECT_STATUSES = {301, 308}


def is_redirect(response) -> bool:
    """True when an httpx/requests-style response is a client-level redirect."""
    if response is None:
        return False
    if getattr(response, 'is_redirect', False):
        return True
    status = getattr(response, 'status_code', None)
    if status is not None and int(status) in REDIRECT_STATUSES:
        return True
    return False


_installed = False


def ensure_httpx_redirect_attributes() -> None:
    """Give httpx.Response the requests-style is_redirect/is_permanent_redirect
    properties so defensive code may use attribute access safely. Idempotent."""
    global _installed
    if _installed:
        return
    try:
        import httpx
    except Exception:
        _installed = True
        return
    cls = httpx.Response
    if not hasattr(cls, 'is_redirect'):
        def _is_redirect(self):
            return self.status_code in REDIRECT_STATUSES
        _is_redirect.__name__ = 'is_redirect'
        cls.is_redirect = property(_is_redirect)
    if not hasattr(cls, 'is_permanent_redirect'):
        def _is_permanent_redirect(self):
            return self.status_code in PERMANENT_REDIRECT_STATUSES
        _is_permanent_redirect.__name__ = 'is_permanent_redirect'
        cls.is_permanent_redirect = property(_is_permanent_redirect)
    _installed = True