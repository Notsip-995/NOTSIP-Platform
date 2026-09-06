from __future__ import annotations
import asyncio, uuid
class JobRunner:
    def __init__(self,store,events): self.store=store; self.events=events; self.handlers={}; self.running=False
    def register(self,name,fn): self.handlers[name]=fn
    async def run_once(self):
        for task in self.store.list_tasks('PENDING')[:10]:
            fn=self.handlers.get(task['data'].get('handler',''))
            if not fn: continue
            self.store.put_task(task['id'],task['objective'],'RUNNING',task['priority'],task['data'])
            try:
                res=fn(task)
                if asyncio.iscoroutine(res): res=await res
                self.store.put_task(task['id'],task['objective'],'COMPLETED',task['priority'],{**task['data'],'result':res})
                from .events import Event
                await self.events.publish(Event('task.completed',{'task_id':task['id'],'result':res}))
            except Exception as e:
                self.store.put_task(task['id'],task['objective'],'FAILED',task['priority'],{**task['data'],'error':str(e)})
    async def loop(self,interval=2):
        self.running=True
        while self.running:
            await self.run_once(); await asyncio.sleep(interval)
    def stop(self): self.running=False
    def create(self,objective,handler,priority=0,data=None):
        tid=str(uuid.uuid4()); self.store.put_task(tid,objective,'PENDING',priority,{**(data or {}),'handler':handler}); return tid
