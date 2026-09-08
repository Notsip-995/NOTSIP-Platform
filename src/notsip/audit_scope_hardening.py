from __future__ import annotations
from fastapi import Depends
from .actor_context import current_actor

def attach(app,require_auth,store,audit_log):
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in {'/api/audit','/api/audit/log'}]
    @app.get('/api/audit')
    async def audit(_:None=Depends(require_auth)):
        actor=current_actor()
        if actor=='primary-user':rows=store.audit_recent()
        else:rows=store.rows('SELECT * FROM audit WHERE user_id=? ORDER BY id DESC LIMIT 200',(actor,))
        return {'audit':rows}
    @app.get('/api/audit/log')
    async def audit_log_route(_:None=Depends(require_auth)):
        actor=current_actor();events=audit_log.tail()
        if actor!='primary-user':events=[x for x in events if str(x.get('actor',''))==actor]
        return {'events':events}
