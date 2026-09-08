from __future__ import annotations
from fastapi import Depends


def attach(app,require_auth,audit_log):
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None)!='/api/audit/verify']
    @app.get('/api/audit/verify')
    async def audit_verify(_:None=Depends(require_auth)):
        result=audit_log.verify()
        return {'status':'SUCCESS' if result.get('valid') else 'FAILURE','verification':result}
