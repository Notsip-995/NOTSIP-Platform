import asyncio
import json


class StoreStub:
    def __init__(self): self.updates=[]
    def task_update(self,*args,**kwargs): self.updates.append((args,kwargs))


class AgentStub:
    def __init__(self): self.calls=[]
    async def run_tool(self,name,args):
        self.calls.append(name)
        return {'status':'SUCCESS','verified':True,'tool':name}
    async def handle(self,objective):
        self.calls.append(objective)
        return {'status':'SUCCESS','verified':True}


def test_durable_workflow_resumes_after_completed_step():
    from notsip.workflow_runtime_hardening import DurableWorkflowEngine
    store=StoreStub();agent=AgentStub();engine=DurableWorkflowEngine(store,agent)
    task={'id':'wf-1','data':json.dumps({'steps':[
        {'id':'one','tool':'tool-a','args':{}},
        {'id':'two','tool':'tool-b','args':{},'depends_on':['one']},
    ],'step_results':[]})}
    first=asyncio.run(engine.run_task(task))
    assert first['status']=='CONTINUE'
    assert agent.calls==['tool-a']
    persisted=json.loads(store.updates[-1][1]['data'])
    task['data']=json.dumps(persisted)
    second=asyncio.run(engine.run_task(task))
    assert second['status']=='CONTINUE' or second['status']=='SUCCESS'
    assert agent.calls.count('tool-a')==1
    assert agent.calls.count('tool-b')==1
