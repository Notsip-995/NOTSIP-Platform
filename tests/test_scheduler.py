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
