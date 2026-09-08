from __future__ import annotations
import json
from fastapi import Depends,HTTPException
from .actor_context import current_actor


def attach(app,require_auth,store,jobs):
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in {'/api/tasks','/api/tasks/{task_id}/run'}]
    def own(task):
        try:data=json.loads(task.get('data') or '{}')
        except Exception:data={}
        return data.get('actor','primary-user')==current_actor()
    @app.get('/api/tasks')
    async def list_tasks(_:None=Depends(require_auth)):
        return {'tasks':[x for x in store.tasks() if own(x)]}
    @app.post('/api/tasks')
    async def create_task(payload:dict,_:None=Depends(require_auth)):
        objective=str(payload.get('objective','')).strip();handler=str(payload.get('handler','agent')).strip()
        if not objective:raise HTTPException(400,'objective is required')
        if handler not in jobs.handlers:raise HTTPException(400,f'unknown task handler: {handler}')
        data=dict(payload.get('data') or {});data.pop('actor',None);data['actor']=current_actor()
        try:tid=jobs.create(objective,handler,float(payload.get('delay',0) or 0),payload.get('interval'),data,int(payload.get('priority',0) or 0),str(payload.get('idempotency_key','') or ''),actor=current_actor())
        except ValueError as exc:raise HTTPException(400,str(exc))
        return {'task_id':tid,'handler':handler,'actor':current_actor()}
    @app.post('/api/tasks/{task_id}/run')
    async def run_task(task_id:str,_:None=Depends(require_auth)):
        task=store.row('SELECT * FROM tasks WHERE id=?',(task_id,))
        if not task or not own(task):raise HTTPException(404,'Task not found')
        store.task_update(task_id,state='PENDING',run_at=0);return {'status':'QUEUED','task_id':task_id,'actor':current_actor()}
