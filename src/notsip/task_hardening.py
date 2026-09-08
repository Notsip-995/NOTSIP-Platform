from __future__ import annotations
import json,time
from fastapi import Depends,HTTPException
from .actor_context import current_actor
from .task_decomposer import TaskDecomposer


def _task_data(payload, actor):
    data=dict(payload.get('data') or {});data.pop('actor',None);context=payload.get('context',data.get('context',{}));constraints=payload.get('constraints',data.get('constraints',[]));required_tools=payload.get('required_tools',data.get('required_tools',[]));permissions=payload.get('permissions',data.get('permissions',[]));subtasks=payload.get('subtasks',data.get('subtasks',[]));verification=payload.get('verification',data.get('verification',{}))
    if not isinstance(context,dict):raise HTTPException(400,'context must be an object')
    for name,value in (('constraints',constraints),('required_tools',required_tools),('permissions',permissions),('subtasks',subtasks)):
        if not isinstance(value,list):raise HTTPException(400,f'{name} must be an array')
    if not isinstance(verification,dict):raise HTTPException(400,'verification must be an object')
    deadline=payload.get('deadline',data.get('deadline'))
    if deadline is not None:
        try:deadline=float(deadline)
        except (TypeError,ValueError):raise HTTPException(400,'deadline must be Unix seconds')
        if deadline<=time.time():raise HTTPException(400,'deadline must be in the future')
    data.update({'actor':actor,'requester':actor,'context':context,'deadline':deadline,'priority':max(0,min(4,int(payload.get('priority',data.get('priority',0)) or 0))),'constraints':constraints,'required_tools':required_tools,'permissions':permissions,'subtasks':subtasks,'verification':verification,'state':data.get('state','PENDING')});return data


def attach(app,require_auth,store,jobs):
    from .app import agent as live_agent
    from .workflow_runtime_hardening import DurableWorkflowEngine
    jobs.agent=live_agent
    decomposer=TaskDecomposer();durable=DurableWorkflowEngine(store,live_agent)

    async def durable_agent_handler(task):
        data=task.get('data') or '{}'
        data=json.loads(data) if isinstance(data,str) else dict(data)
        subtasks=data.get('subtasks') or []
        if not subtasks:
            return await live_agent.handle(task.get('objective',''))
        workflow_data=dict(data)
        normalized_steps=[]
        for step in subtasks:
            if not isinstance(step,dict):raise ValueError('workflow subtask must be an object')
            normalized=dict(step)
            if 'dependencies' in normalized and 'depends_on' not in normalized:
                normalized['depends_on']=list(normalized.pop('dependencies') or [])
            normalized_steps.append(normalized)
        workflow_data['steps']=normalized_steps
        workflow_data.setdefault('step_results',[])
        return await durable.run_task(dict(task,data=json.dumps(workflow_data)))

    jobs.register('agent',durable_agent_handler)
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in {'/api/tasks','/api/tasks/{task_id}/run'}]
    def own(task):
        try:data=json.loads(task.get('data') or '{}')
        except Exception:data={}
        return data.get('actor','primary-user')==current_actor()
    @app.get('/api/tasks')
    async def list_tasks(_:None=Depends(require_auth)):return {'tasks':[x for x in store.tasks() if own(x)]}
    @app.post('/api/tasks')
    async def create_task(payload:dict,_:None=Depends(require_auth)):
        actor=current_actor();objective=str(payload.get('objective','')).strip();handler=str(payload.get('handler','agent')).strip()
        if not objective:raise HTTPException(400,'objective is required')
        if handler not in jobs.handlers:raise HTTPException(400,f'unknown task handler: {handler}')
        explicit_subtasks='subtasks' in payload or bool((payload.get('data') or {}).get('subtasks'))
        data=_task_data(payload,actor)
        if not data['subtasks'] and handler=='agent' and not explicit_subtasks:
            plan=decomposer.decompose(objective)
            if plan.get('status')=='SUCCESS':
                data['subtasks']=plan.get('subtasks',[]);data['context']['decomposition']={'status':'SUCCESS','completion_condition':plan.get('completion_condition'),'critical_path':decomposer.critical_path(plan)}
        if len(data['subtasks'])>50:raise HTTPException(400,'too many subtasks')
        try:tid=jobs.create(objective,handler,float(payload.get('delay',0) or 0),payload.get('interval'),data,data['priority'],str(payload.get('idempotency_key','') or ''),actor=actor)
        except ValueError as exc:raise HTTPException(400,str(exc))
        return {'status':'SUCCESS','task_id':tid,'handler':handler,'actor':actor,'requester':actor,'context':data['context'],'deadline':data['deadline'],'priority':data['priority'],'constraints':data['constraints'],'required_tools':data['required_tools'],'permissions':data['permissions'],'subtasks':data['subtasks'],'state':data['state'],'verification':data['verification']}
    @app.post('/api/tasks/{task_id}/run')
    async def run_task(task_id:str,_:None=Depends(require_auth)):
        placeholder='%s' if getattr(store,'_backend',None) else '?'
        task=store.row(f'SELECT * FROM tasks WHERE id={placeholder}',(task_id,))
        if not task or not own(task):raise HTTPException(404,'Task not found')
        store.task_update(task_id,state='PENDING',run_at=0);return {'status':'QUEUED','task_id':task_id,'actor':current_actor()}
