import asyncio
import json


class StoreStub:
    def __init__(self): self.updates=[]
    def task_update(self,*args,**kwargs): self.updates.append((args,kwargs))


class AgentStub:
    def __init__(self): self.calls=[]
    async def handle(self,objective):
        self.calls.append(objective)
        return {'status':'SUCCESS','verified':True}
    async def run_tool(self,name,args):
        self.calls.append(name)
        return {'status':'SUCCESS','verified':True}


def test_agent_task_handler_executes_persisted_subtasks():
    from notsip.task_hardening import attach
    from notsip.workflow_runtime_hardening import DurableWorkflowEngine
    store=StoreStub();agent=AgentStub()
    class Jobs:
        def __init__(self):self.handlers={}
        def register(self,name,fn):self.handlers[name]=fn
    jobs=Jobs()
    # Exercise the durable handler logic without constructing FastAPI routes.
    data={'subtasks':[{'id':1,'objective':'first step','dependencies':[]},{'id':2,'objective':'second step','dependencies':[1]}]}
    engine=DurableWorkflowEngine(store,agent)
    result=asyncio.run(engine.run_task({'id':'task-1','data':json.dumps(data)}))
    assert result['status']=='CONTINUE'
    assert agent.calls==['first step']
    persisted=json.loads(store.updates[-1][1]['data'])
    persisted['subtasks']=data['subtasks']
    second=asyncio.run(engine.run_task({'id':'task-1','data':json.dumps(persisted)}))
    assert second['status']=='SUCCESS'
    assert agent.calls==['first step','second step']
