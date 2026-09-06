from __future__ import annotations
import asyncio,inspect,time
class Scheduler:
    def __init__(self,store):self.store=store;self.handlers={};self.running=True
    def register(self,name,fn):self.handlers[name]=fn
    def create(self,objective,handler='',delay=0,interval=None,data=None,priority=0):return self.store.task(objective,'PENDING',priority,handler,data,time.time()+delay,interval)
    async def tick(self):
        for t in self.store.tasks('PENDING'):
            if t.get('run_at') and t['run_at']>time.time():continue
            fn=self.handlers.get(t['handler'])
            if not fn:self.store.task_update(t['id'],state='FAILED',error='no handler registered');continue
            self.store.task_update(t['id'],state='RUNNING')
            try:
                r=fn(t)
                if inspect.isawaitable(r):await r
                if t.get('interval_sec'):self.store.task_update(t['id'],state='PENDING',run_at=time.time()+t['interval_sec'])
                else:self.store.task_update(t['id'],state='COMPLETED')
            except Exception as e:self.store.task_update(t['id'],state='FAILED',error=str(e))
    async def loop(self):
        while self.running:await self.tick();await asyncio.sleep(1)
    def stop(self):self.running=False
