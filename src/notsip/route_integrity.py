from __future__ import annotations


def normalize(app):
    """Keep the last registered handler for each path/method combination.

    Hardening layers attach replacements after legacy runtime handlers.
    Scanning in reverse preserves the newest canonical handler and removes
    only older duplicates.
    """
    seen=set()
    kept=[]
    for route in reversed(app.router.routes):
        path=getattr(route,'path',None)
        methods=frozenset(getattr(route,'methods',set()) or set())
        key=(path,methods)
        if path is not None and key in seen:
            continue
        if path is not None:
            seen.add(key)
        kept.append(route)
    app.router.routes=list(reversed(kept))
