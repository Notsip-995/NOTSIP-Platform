from __future__ import annotations
import asyncio, inspect, time

class Scheduler:
    def __init__(self, store):
        self.store = store
        self.handlers = {}
        self.running = True

    def register(self, name, fn):
        self.handlers[name] = fn

    def create(self, objective, handler='agent', delay=0, interval=None, data=None, priority=0):
        return self.store.task(objective, 'PENDING', priority, handler or 'agent', data, time.time() + delay, interval)

    async def run_one(self, task):
        fn = self.handlers.get(task.get('handler') or 'agent')
        if not fn:
            self.store.task_update(task['id'], state='FAILED', error=f"no handler registered: {task.get('handler') or 'agent'}")
            return {'status':'FAILURE','error':'no handler registered'}
        self.store.task_update(task['id'], state='RUNNING')
        try:
            result = fn(task)
            if inspect.isawaitable(result):
                result = await result
            if task.get('interval_sec'):
                self.store.task_update(task['id'], state='PENDING', run_at=time.time() + task['interval_sec'], error='')
            else:
                self.store.task_update(task['id'], state='COMPLETED', error='')
            return {'status':'SUCCESS','result':result}
        except Exception as exc:
            self.store.task_update(task['id'], state='FAILED', error=str(exc))
            return {'status':'FAILURE','error':str(exc)}

    async def tick(self):
        now = time.time()
        for task in self.store.tasks('PENDING'):
            if task.get('run_at') and task['run_at'] > now:
                continue
            await self.run_one(task)

    async def loop(self):
        while self.running:
            await self.tick()
            await asyncio.sleep(1)

    def stop(self):
        self.running = False
