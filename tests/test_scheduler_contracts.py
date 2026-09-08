import asyncio
import json
import time


class StoreStub:
    def __init__(self):
        self.updates=[]
    def tasks(self, state=None): return []
    def task_update(self,*args,**kwargs): self.updates.append((args,kwargs))
    def claim_task(self,*args,**kwargs): return True


class RegistryStub:
    def __init__(self, names): self.names=set(names)
    def get(self, name): return object() if name in self.names else None


class AgentStub:
    def __init__(self, names): self.registry=RegistryStub(names)


def test_deadline_is_enforced_before_execution():
    from notsip.jobs import Scheduler
    store=StoreStub(); s=Scheduler(store); s.agent=AgentStub({'ok'})
    task={'id':'t1','handler':'ok','data':json.dumps({'deadline':time.time()-1,'verification':{}})}
    result=asyncio.run(s.run_one(task))
    assert result['status']=='FAILURE'
    assert 'deadline' in result['error']


def test_missing_concrete_required_tool_fails():
    from notsip.jobs import Scheduler
    store=StoreStub(); s=Scheduler(store); s.agent=AgentStub({'other'}); s.register('agent',lambda task: {'status':'SUCCESS','verified':True})
    task={'id':'t2','handler':'agent','data':json.dumps({'required_tools':['missing-tool'],'verification':{'required':True}})}
    result=asyncio.run(s.run_one(task))
    assert result['status']=='FAILURE'
    assert 'required tools unavailable' in result['error']


def test_scheduler_persists_unverified_outcome():
    from notsip.jobs import Scheduler
    store=StoreStub(); s=Scheduler(store); s.agent=AgentStub(set()); s.register('agent',lambda task: {'status':'SUCCESS'})
    task={'id':'t3','handler':'agent','data':json.dumps({'verification':{'required':True}})}
    result=asyncio.run(s.run_one(task))
    assert result['status']=='SUCCESS'
    payload=store.updates[-1][1]['data']
    data=json.loads(payload)
    assert data['verification']['verified'] is False
    assert data['verification']['status']=='UNVERIFIED'


def test_task_idempotency_is_scoped_by_actor(tmp_path):
    from notsip.jobs import Scheduler
    from notsip.store import Store

    store=Store(tmp_path)
    scheduler=Scheduler(store)
    first=scheduler.create('same request','agent',actor='actor-a',idempotency_key='same-key')
    repeat=scheduler.create('same request','agent',actor='actor-a',idempotency_key='same-key')
    other=scheduler.create('same request','agent',actor='actor-b',idempotency_key='same-key')

    assert first==repeat
    assert other!=first
    rows=store.tasks()
    by_id={row['id']:json.loads(row['data']) for row in rows}
    assert by_id[first]['actor']=='actor-a'
    assert by_id[other]['actor']=='actor-b'
    assert by_id[first]['idempotency_key']=='same-key'
    assert by_id[other]['idempotency_key']=='same-key'
