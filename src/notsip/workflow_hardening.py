from __future__ import annotations
import json
from fastapi import Depends, HTTPException
from .actor_context import current_actor
from .workflows import WorkflowEngine


def attach(app, require_auth, agent, jobs, store):
    engine = WorkflowEngine(agent, store)
    if 'workflow' not in jobs.handlers:
        jobs.register('workflow', engine.run)

    @app.post('/api/workflows')
    async def create_workflow(payload: dict, _: None = Depends(require_auth)):
        objective = str(payload.get('objective','')).strip()
        if not objective:
            raise HTTPException(400, 'objective is required')
        steps = engine.normalize(payload.get('steps'))
        data = {
            'actor': current_actor(),
            'steps': steps,
            'current_step': 0,
            'step_results': [],
        }
        task_id = jobs.create(
            objective,
            'workflow',
            float(payload.get('delay',0) or 0),
            None,
            data,
            int(payload.get('priority',0) or 0),
            str(payload.get('idempotency_key','') or ''),
            actor=current_actor(),
        )
        return {'status':'SUCCESS','workflow_task_id':task_id,'actor':current_actor(),'steps':steps}

    @app.get('/api/workflows/{task_id}')
    async def get_workflow(task_id: str, _: None = Depends(require_auth)):
        task = store.row('SELECT * FROM tasks WHERE id=?', (task_id,))
        if not task:
            raise HTTPException(404, 'workflow not found')
        try:
            data = json.loads(task.get('data') or '{}')
        except Exception:
            data = {}
        if data.get('actor','primary-user') != current_actor():
            raise HTTPException(404, 'workflow not found')
        return {'task':task,'workflow':data}

    return engine
