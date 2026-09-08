from __future__ import annotations
import json
from .system_services import WorkflowEngine


def attach(jobs, store, agent):
    engine = WorkflowEngine(store, agent)

    async def workflow_handler(task):
        data = task.get('data') or {}
        if isinstance(data, str):
            data = json.loads(data or '{}')
        steps = data.get('steps') or []
        return await engine.run(steps)

    jobs.register('workflow', workflow_handler)
    return engine
