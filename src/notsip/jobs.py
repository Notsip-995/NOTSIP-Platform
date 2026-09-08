from __future__ import annotations
import asyncio, inspect, json, os, socket, time, uuid

class Scheduler:
    def __init__(self,store,events=None):
        self.store=store; self.events=events; self.handlers={}; self.running=True; self.max_retries=4; self.worker_id=f'{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}'; self.reclaim_after=300; self._active_tasks=set()
        self._recover_stale()
    def _recover_stale(self):
        now=time.time()
        for task in self.store.tasks('RUNNING'):
            if task.get('id') in self._active_tasks:continue
            data=_json(task.get('data'));started=float(data.get('started_at',0) or 0)
            if started and now-started>self.reclaim_after:
                data.update({'recovered_from':data.get('worker_id'),'recovered_at':now})
                self.store.task_update(task['id'],state='PENDING',run_at=now,data=json.dumps(data),error='reclaimed after worker timeout')
    def register(self,name,fn):self.handlers[name]=fn
    def create(self,objective,handler='agent',delay=0,interval=None,data=None,priority=0,idempotency_key=''):
        delay=max(0.0,float(delay or 0));interval=None if interval is None else float(interval)
        if interval is not None and not 5<=interval<=30*86400:raise ValueError('interval must be between 5 seconds and 30 days')
        priority=max(0,min(4,int(priority or 0)));payload=dict(data or {});key=idempotency_key or uuid.uuid4().hex;payload.setdefault('max_retries',self.max_retries);payload.setdefault('idempotency_key',key)
        return self.store.task(objective,'PENDING',priority,handler or 'agent',payload,time.time()+delay,interval,key)
    async def _publish(self,event_type,payload):
        if self.events is None:return []
        try:
            from .events import Event
            return await self.events.publish(Event(event_type,payload,'scheduler'))
        except Exception as exc:
            return [{'kind':'event_publish','error':str(exc),'event':event_type}]
    async def run_one(self,task):
        handler=task.get('handler') or 'agent';fn=self.handlers.get(handler)
        if not fn:
            self.store.task_update(task['id'],state='FAILED',error=f'no handler registered: {handler}')
            await self._publish('task.failed',{'task_id':task['id'],'objective':task.get('objective',''),'handler':handler,'error':f'no handler registered: {handler}','attempt':int(task.get('retries') or 0) + 1})
            return {'status':'FAILURE','error':'no handler registered'}
        execution_id=uuid.uuid4().hex;started=time.time();payload=_json(task.get('data'));payload.update({'worker_id':self.worker_id,'started_at':started,'execution_id':execution_id})
        claimed=self.store.claim_task(task['id'],json.dumps(payload))
        if not claimed:return {'status':'SKIPPED','reason':'task already claimed'}
        self._active_tasks.add(task['id'])
        try:
            result=fn(dict(task, data=json.dumps(payload)))
            if inspect.isawaitable(result):result=await result
            payload.update({'finished_at':time.time(),'last_result':result})
            if task.get('interval_sec'):
                self.store.task_update(task['id'],state='PENDING',run_at=time.time()+task['interval_sec'],data=json.dumps(payload),error='')
            else:
                self.store.task_update(task['id'],state='COMPLETED',data=json.dumps(payload),error='')
            event_errors=await self._publish('task.completed',{'task_id':task['id'],'objective':task.get('objective',''),'handler':handler,'execution_id':execution_id,'result':result,'task_data':payload,'recurring':bool(task.get('interval_sec'))})
            if event_errors:
                payload['event_publish_errors']=event_errors;self.store.task_update(task['id'],data=json.dumps(payload))
            return {'status':'SUCCESS','result':result,'execution_id':execution_id,'event_publish_errors':event_errors}
        except Exception as exc:
            retries=int(task.get('retries') or 0)+1;max_retries=int(payload.get('max_retries',self.max_retries));payload.update({'last_error':str(exc),'failed_at':time.time()})
            if retries<=max_retries:
                backoff=min(900,2**min(retries,9));self.store.task_update(task['id'],state='PENDING',run_at=time.time()+backoff,retries=retries,data=json.dumps(payload),error=str(exc));event_errors=await self._publish('task.retrying',{'task_id':task['id'],'objective':task.get('objective',''),'handler':handler,'execution_id':execution_id,'error':str(exc),'retry':retries,'backoff':backoff,'task_data':payload});return {'status':'RETRYING','error':str(exc),'retry':retries,'backoff':backoff,'event_publish_errors':event_errors}
            self.store.task_update(task['id'],state='FAILED',data=json.dumps(payload),error=str(exc),retries=retries);event_errors=await self._publish('task.failed',{'task_id':task['id'],'objective':task.get('objective',''),'handler':handler,'execution_id':execution_id,'error':str(exc),'retries':retries,'task_data':payload});return {'status':'FAILURE','error':str(exc),'retries':retries,'event_publish_errors':event_errors}
        finally:self._active_tasks.discard(task['id'])
    async def tick(self):
        self._recover_stale();now=time.time()
        for task in self.store.tasks('PENDING'):
            if task.get('run_at') and task['run_at']>now:continue
            await self.run_one(task)
    async def loop(self):
        while self.running:
            await self.tick();await asyncio.sleep(1)
    def stop(self):self.running=False

def _json(value):
    try:return json.loads(value or '{}')
    except Exception:return {}
