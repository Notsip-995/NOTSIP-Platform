from __future__ import annotations
from fastapi import Depends
from .actor_context import current_actor
from .memory_service import MemoryService


def attach(app, require_auth, store):
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in {'/api/memory/lifecycle','/api/memory/maintain'}]
    def service():return MemoryService(store,current_actor())
    @app.get('/api/memory/lifecycle')
    async def memory_lifecycle(_:None=Depends(require_auth)):
        return service().snapshot()
    @app.post('/api/memory/maintain')
    async def memory_maintain(_:None=Depends(require_auth)):
        current=service();return {'decay':current.decay(),'consolidation':current.consolidate()}
