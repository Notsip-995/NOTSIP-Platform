from __future__ import annotations
from fastapi import Depends,HTTPException
from .recovery_state_hardening import restore as restore_user_state,validate as validate_user_state

def attach(app, *, require_auth, recovery, store):
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None)!='/api/recovery/restore']
    @app.post('/api/recovery/restore')
    async def restore(payload:dict,_:None=Depends(require_auth)):
        if not bool(payload.get('confirm')):raise HTTPException(400,'explicit confirmation required')
        state=recovery.latest()
        if not state:raise HTTPException(404,'no recovery checkpoint available')
        user_state=state.get('user_state') or {}
        try:validate_user_state(user_state)
        except Exception as exc:raise HTTPException(409,f'checkpoint user state is invalid: {exc}')
        existing={r['id']:r.get('token_hash','') for r in store.rows('SELECT id,token_hash FROM devices')}
        result=store.restore_runtime_state(state)
        if user_state:
            try:result.update(restore_user_state(__import__('pathlib').Path(recovery.root),user_state))
            except Exception as exc:raise HTTPException(500,f'storage restored but durable user state could not be restored: {exc}')
        repaired=[]
        for device_id,token_hash in existing.items():
            current=store.row('SELECT token_hash FROM devices WHERE id=?',(device_id,))
            if token_hash and store.row('SELECT id FROM devices WHERE id=?',(device_id,)) and not (current or {}).get('token_hash',''):
                store.exec("UPDATE devices SET token_hash=?,status=CASE WHEN status='REPAIR_REQUIRED' THEN 'ONLINE' ELSE status END WHERE id=?",(token_hash,device_id));repaired.append(device_id)
        if isinstance(result,dict) and repaired:result['devices_repaired']=repaired
        return {'status':'RESTORED','checkpoint':state,'result':result}
