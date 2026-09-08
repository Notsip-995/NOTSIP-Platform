import asyncio
import json
from pathlib import Path


def test_task_hardening_registers_durable_agent_handler():
    text=Path('src/notsip/task_hardening.py').read_text(encoding='utf-8')
    assert 'DurableWorkflowEngine' in text
    assert "jobs.register('agent',durable_agent_handler)" in text
    assert "normalized['depends_on']=list(normalized.pop('dependencies') or [])" in text


class StoreStub:
    def __init__(self): self.updates=[]
    def task_update(self,*args,**kwargs): self.updates.append((args,kwargs))


class AgentStub:
    def __init__(self): self.calls=[]
    async def handle(self,objective):
        self.calls.append(objective)
        return {'status':'SUCCESS','verified':True}


def test_decomposed_workflow_resumes_without_replaying_previous_step():
    from notsip.workflow_runtime_hardening import DurableWorkflowEngine
    store=StoreStub();agent=AgentStub();engine=DurableWorkflowEngine(store,agent)
    data={'steps':[{'id':1,'objective':'first step'},{'id':2,'objective':'second step','depends_on':[1]}],'step_results':[]}
    first=asyncio.run(engine.run_task({'id':'task-1','data':json.dumps(data)}))
    assert first['status']=='CONTINUE';assert agent.calls==['first step']
    persisted=json.loads(store.updates[-1][1]['data'])
    second=asyncio.run(engine.run_task({'id':'task-1','data':json.dumps(persisted)}))
    assert second['status']=='SUCCESS';assert agent.calls==['first step','second step']
