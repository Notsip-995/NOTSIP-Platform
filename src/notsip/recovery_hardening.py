from __future__ import annotations
from fastapi import Depends, HTTPException

def attach(app, *, require_auth, recovery, store):
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None)!='/api/recovery/restore']
    @app.post('/api/recovery/restore')
    async def restore(payload:dict,_:None=Depends(require_auth)):
        if not bool(payload.get('confirm')):
            raise HTTPException(400,'explicit confirmation required')
        state=recovery.latest()
        if not state:raise HTTPException(404,'no recovery checkpoint available')
        result=store.restore_runtime_state(state)
        return {'status':'RESTORED','checkpoint':state,'result':result}
