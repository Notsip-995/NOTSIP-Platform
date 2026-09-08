from __future__ import annotations
from pathlib import Path
from fastapi import Depends, HTTPException
from .actor_context import current_actor
from .forensics import Forensics
from .actor_workspace import ActorWorkspace


def attach(app, require_auth, data_root):
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in {'/api/forensics/scan','/api/forensics/investigate'}]
    manager=ActorWorkspace(Path(data_root).resolve() / 'workspace')
    def service():return Forensics(manager.for_actor(current_actor()).root)
    @app.get('/api/forensics/scan')
    async def scan(q:str='',limit:int=1000,_:None=Depends(require_auth)):
        return service().scan(q,limit)
    @app.get('/api/forensics/investigate')
    async def investigate(q:str='',since:float|None=None,until:float|None=None,limit:int=1000,_:None=Depends(require_auth)):
        if since is not None and until is not None and until<since:raise HTTPException(400,'until must be >= since')
        return service().investigate(q,since,until,limit)
