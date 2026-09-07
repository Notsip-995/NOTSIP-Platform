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
        existing={r['id']:r.get('token_hash','') for r in store.rows('SELECT id,token_hash FROM devices')}
        result=store.restore_runtime_state(state)
        repaired=[]
        for device_id,token_hash in existing.items():
            if token_hash and store.row('SELECT id FROM devices WHERE id=?',(device_id,)) and not store.row('SELECT token_hash FROM devices WHERE id=?',(device_id,)).get('token_hash',''):
                store.exec('UPDATE devices SET token_hash=?,status=CASE WHEN status=\'REPAIR_REQUIRED\' THEN \'ONLINE\' ELSE status END WHERE id=?',(token_hash,device_id));repaired.append(device_id)
        if isinstance(result,dict) and repaired:result['devices_repaired']=repaired
        return {'status':'RESTORED','checkpoint':state,'result':result}
