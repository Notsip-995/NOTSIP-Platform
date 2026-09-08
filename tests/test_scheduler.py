import asyncio
from notsip.jobs import Scheduler
from notsip.store import Store


def test_scheduler_agent_handler_runs(tmp_path):
    store=Store(tmp_path)
    scheduler=Scheduler(store)
    seen=[]
    async def handler(task):
        seen.append(task['objective'])
        return {'ok':True}
    scheduler.register('agent', handler)
    tid=scheduler.create('hello', 'agent', delay=0)
    asyncio.run(scheduler.tick())
    assert seen==['hello']
    assert store.row('SELECT state FROM tasks WHERE id=?',(tid,))['state']=='COMPLETED'


def test_task_claim_is_single_winner(tmp_path):
    store=Store(tmp_path)
    tid=store.task('once','PENDING',0,'agent',{},0,None)
    assert store.claim_task(tid,'{"worker":"a"}') is True
    assert store.claim_task(tid,'{"worker":"b"}') is False
    assert store.row('SELECT state,data FROM tasks WHERE id=?',(tid,))['state']=='RUNNING'


def test_scheduler_idempotency_key_reuses_existing_task(tmp_path):
    store=Store(tmp_path)
    scheduler=Scheduler(store)
    first=scheduler.create('same work','agent',idempotency_key='request-123')
    second=scheduler.create('same work again','agent',idempotency_key='request-123')
    assert second==first
    rows=store.rows('SELECT id,idempotency_key FROM tasks WHERE idempotency_key=?',('request-123',))
    assert len(rows)==1
