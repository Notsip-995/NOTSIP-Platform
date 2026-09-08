import asyncio,inspect,json,os,socket,time,uuid,hashlib
from .actor_context import current_actor,set_actor,reset_actor

class Scheduler:
    def __init__(self,store,events=None):
        self.store=store;self.events=events;self.handlers={};self.agent=None;self.running=True;self.max_retries=4;self.worker_id=f'{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}';self.reclaim_after=300;self._active_tasks=set();self._recover_stale()
    def _recover_stale(self):
        now=time.time()
        for task in self.store.tasks('RUNNING'):
            if task.get('id') in self._active_tasks:continue
            data=_json(task.get('data'));started=float(data.get('started_at',0) or 0)
            if started and now-started>self.reclaim_after:
                data.update({'recovered_from':data.get('worker_id'),'recovered_at':now,'state':'PENDING'});self.store.task_update(task['id'],state='PENDING',run_at=now,data=json.dumps(data),error='reclaimed after worker timeout')
    def register(self,name,fn):self.handlers[name]=fn
    @staticmethod
    def _storage_idempotency_key(actor,key):
        return hashlib.sha256(f'{actor}\0{key}'.encode('utf-8')).hexdigest()
    def create(self,objective,handler='agent',delay=0,interval=None,data=None,priority=0,idempotency_key='',actor=None):
        delay=max(0.0,float(delay or 0));interval=None if interval is None else float(interval)
        if interval is not None and not 5<=interval<=30*86400:raise ValueError('interval must be between 5 seconds and 30 days')
        priority=max(0,min(4,int(priority or 0)));payload=dict(data or {});actor_id=str(actor or payload.get('actor') or current_actor()).strip() or 'primary-user';payload.setdefault('actor',actor_id);payload.setdefault('requester',payload.get('actor'));payload.setdefault('state','PENDING');payload.setdefault('result',{});payload.setdefault('verification',{});key=idempotency_key or uuid.uuid4().hex;payload.setdefault('idempotency_key',key);payload.setdefault('max_retries',self.max_retries);storage_key=self._storage_idempotency_key(actor_id,key) if idempotency_key else key;return self.store.task(objective,'PENDING',priority,handler or 'agent',payload,time.time()+delay,interval,storage_key)
    async def _publish(self,event_type,payload):
        if self.events is None:return []
        try:
            from .events import Event
            return await self.events.publish(Event(event_type,payload,'scheduler'))
        except Exception as exc:return [{'kind':'event_publish','error':str(exc),'event':event_type}]
    @staticmethod
    def _outcome_metadata(payload,result,status):
        payload['state']=status;payload['result']=result if isinstance(result,dict) else {'value':result};verification=payload.get('verification') or {};verification['required']=bool(verification.get('required',False));verification['verified']=bool(isinstance(result,dict) and result.get('verified') is True);verification['status']='VERIFIED' if verification['verified'] else 'UNVERIFIED';payload['verification']=verification;return payload
    def _contract_error(self,payload):
        deadline=payload.get('deadline')
        if deadline is not None:
            try:
                if time.time()>float(deadline):return 'task deadline expired'
            except (TypeError,ValueError):return 'invalid task deadline'
        registry=getattr(self.agent,'registry',None);required=[str(x) for x in (payload.get('required_tools') or [])]
        if registry is None:return ''
        missing=[name for name in required if registry.get(name) is None]
        return f'required tools unavailable: {missing}' if missing else ''
    async def run_one(self,task):
        handler=task.get('handler') or 'agent';fn=self.handlers.get(handler)
        if not fn:
            self.store.task_update(task['id'],state='FAILED',error=f'no handler registered: {handler}');await self._publish('task.failed',{'task_id':task['id'],'objective':task.get('objective',''),'handler':handler,'error':'no handler registered','attempt':int(task.get('retries') or 0)+1});return {'status':'FAILURE','error':'no handler registered'}
        execution_id=uuid.uuid4().hex;started=time.time();payload=_json(task.get('data'));payload.update({'worker_id':self.worker_id,'started_at':started,'execution_id':execution_id});contract_error=self._contract_error(payload)
        if contract_error:
            payload.update({'state':'FAILED','result':{'status':'FAILURE','error':contract_error},'verification':{'required':bool(payload.get('verification',{}).get('required',False)),'verified':False,'status':'UNVERIFIED'}});self.store.task_update(task['id'],state='FAILED',data=json.dumps(payload),error=contract_error);await self._publish('task.failed',{'task_id':task['id'],'objective':task.get('objective',''),'handler':handler,'error':contract_error,'actor':payload.get('actor','primary-user')});return {'status':'FAILURE','error':contract_error}
        claimed=self.store.claim_task(task['id'],json.dumps(payload))
        if not claimed:return {'status':'SKIPPED','reason':'task already claimed'}
        self._active_tasks.add(task['id']);actor=str(payload.get('actor') or 'primary-user');token=set_actor(actor)
        try:
            result=fn(dict(task,data=json.dumps(payload)))
            if inspect.isawaitable(result):result=await result
            status=str(result.get('status','SUCCESS')) if isinstance(result,dict) else 'SUCCESS';payload['finished_at']=time.time();payload['last_result']=result;self._outcome_metadata(payload,result,status)
            if status=='CONTINUE':
                payload['state']='PENDING';self.store.task_update(task['id'],state='PENDING',run_at=float((result.get('run_at') if isinstance(result,dict) else None) or time.time()),data=json.dumps(payload),error='');event_errors=await self._publish('task.continued',{'task_id':task['id'],'objective':task.get('objective',''),'handler':handler,'execution_id':execution_id,'result':result,'task_data':payload,'actor':actor});
                if event_errors:payload['event_publish_errors']=event_errors;self.store.task_update(task['id'],data=json.dumps(payload))
                return {'status':'CONTINUE','result':result,'execution_id':execution_id,'event_publish_errors':event_errors}
            if status in {'UNKNOWN','PARTIAL_SUCCESS'}:self.store.task_update(task['id'],state=status,data=json.dumps(payload),error='' if status=='PARTIAL_SUCCESS' else str(result.get('error','')) if isinstance(result,dict) else '')
            elif task.get('interval_sec'):payload['state']='PENDING';self.store.task_update(task['id'],state='PENDING',run_at=time.time()+task['interval_sec'],data=json.dumps(payload),error='')
            else:self.store.task_update(task['id'],state='COMPLETED',data=json.dumps(payload),error='')
            event_type='task.completed' if status=='SUCCESS' else 'task.unknown' if status=='UNKNOWN' else 'task.partial';event_errors=await self._publish(event_type,{'task_id':task['id'],'objective':task.get('objective',''),'handler':handler,'execution_id':execution_id,'result':result,'task_data':payload,'recurring':bool(task.get('interval_sec')),'actor':actor})
            if event_errors:payload['event_publish_errors']=event_errors;self.store.task_update(task['id'],data=json.dumps(payload))
            return {'status':status,'result':result,'execution_id':execution_id,'event_publish_errors':event_errors}
        except Exception as exc:
            retries=int(task.get('retries') or 0)+1;max_retries=int(payload.get('max_retries',self.max_retries));payload.update({'last_error':str(exc),'failed_at':time.time(),'state':'PENDING' if retries<=max_retries else 'FAILED','result':{'status':'FAILURE','error':str(exc)}});verification=payload.get('verification') or {};verification['status']='UNVERIFIED';verification['verified']=False;payload['verification']=verification
            if retries<=max_retries:
                backoff=min(900,2**min(retries,9));self.store.task_update(task['id'],state='PENDING',run_at=time.time()+backoff,retries=retries,data=json.dumps(payload),error=str(exc));event_errors=await self._publish('task.retrying',{'task_id':task['id'],'objective':task.get('objective',''),'handler':handler,'execution_id':execution_id,'error':str(exc),'retry':retries,'backoff':backoff,'task_data':payload,'actor':actor});return {'status':'RETRYING','error':str(exc),'retry':retries,'backoff':backoff,'event_publish_errors':event_errors}
            self.store.task_update(task['id'],state='FAILED',data=json.dumps(payload),error=str(exc),retries=retries);event_errors=await self._publish('task.failed',{'task_id':task['id'],'objective':task.get('objective',''),'handler':handler,'execution_id':execution_id,'error':str(exc),'retries':retries,'task_data':payload,'actor':actor});return {'status':'FAILURE','error':str(exc),'retries':retries,'event_publish_errors':event_errors}
        finally:self._active_tasks.discard(task['id']);reset_actor(token)
    async def tick(self):
        self._recover_stale();now=time.time()
        for task in self.store.tasks('PENDING'):
            if task.get('run_at') and task['run_at']>now:continue
            await self.run_one(task)
    async def loop(self):
        while self.running:await self.tick();await asyncio.sleep(1)
    def stop(self):self.running=False

def _json(value):
    try:return json.loads(value or '{}')
    except Exception:return {}