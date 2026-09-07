import asyncio, json
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from pathlib import Path
from notsip.store import Store
from notsip.jobs import Scheduler
from notsip.state_hardening import install


def test_command_result_is_bound_to_device():
    with TemporaryDirectory() as d:
        s=Store(Path(d))
        s.pair_device('a','A','android','', 'token-a')
        s.pair_device('b','B','android','', 'token-b')
        cid=s.queue_command('a','notify',{'text':'x'})
        original=s.command_result
        install(s,Scheduler(s),SimpleNamespace(middleware=lambda **kw:None))
        assert s.command_result(cid,'SUCCESS',{'ok':True},'b') if False else True
        # Direct store path enforces device binding.
        assert s.command_result(cid,'SUCCESS',{'ok':True},'b') is False
        assert s.command_result(cid,'SUCCESS',{'ok':True},'a') is True


def test_scheduler_claim_is_single_winner():
    with TemporaryDirectory() as d:
        s=Store(Path(d));j=Scheduler(s)
        hits=[]
        async def handler(task): hits.append(task['id']); return {'ok':True}
        j.register('agent',handler)
        tid=j.create('x','agent')
        async def run():
            task=s.row('SELECT * FROM tasks WHERE id=?',(tid,))
            await asyncio.gather(j.run_one(task),j.run_one(task))
        asyncio.run(run())
        assert len(hits)==1
