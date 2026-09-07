from __future__ import annotations
import json, inspect, os, socket, time, uuid


def install(store, jobs, app):
    """Install transactional task/device state transitions on a live Store/Scheduler."""
    def _claim_task(task_id, payload):
        now=time.time()
        if getattr(store,'_backend',None):
            with store._backend.conn() as c:
                row=c.execute('UPDATE tasks SET state=%s,data=%s,updated=%s,error=%s WHERE id=%s AND state=%s RETURNING *',('RUNNING',json.dumps(payload),now,'',task_id,'PENDING')).fetchone()
                return dict(row) if row else None
        with store.lock, store.conn() as c:
            cur=c.execute("UPDATE tasks SET state='RUNNING',data=?,updated=?,error='' WHERE id=? AND state='PENDING'",(json.dumps(payload),now,task_id))
            if cur.rowcount!=1:return None
            row=c.execute('SELECT * FROM tasks WHERE id=?',(task_id,)).fetchone();return dict(row) if row else None

    async def run_one(task):
        handler=task.get('handler') or 'agent';fn=jobs.handlers.get(handler)
        if not fn:
            store.task_update(task['id'],state='FAILED',error=f'no handler registered: {handler}')
            return {'status':'FAILURE','error':'no handler registered'}
        payload=_json(task.get('data'));payload.update({'worker_id':jobs.worker_id,'started_at':time.time(),'execution_id':uuid.uuid4().hex})
        claimed=_claim_task(task['id'],payload)
        if not claimed:return {'status':'SKIPPED','reason':'task already claimed'}
        try:
            result=fn(claimed)
            if inspect.isawaitable(result):result=await result
            payload.update({'finished_at':time.time(),'last_result':result})
            if claimed.get('interval_sec'):store.task_update(task['id'],state='PENDING',run_at=time.time()+claimed['interval_sec'],data=json.dumps(payload),error='')
            else:store.task_update(task['id'],state='COMPLETED',data=json.dumps(payload),error='')
            return {'status':'SUCCESS','result':result,'execution_id':payload['execution_id']}
        except Exception as exc:
            retries=int(claimed.get('retries') or 0)+1;max_retries=int(payload.get('max_retries',jobs.max_retries));payload.update({'last_error':str(exc),'failed_at':time.time()})
            if retries<=max_retries:
                backoff=min(900,2**min(retries,9));store.task_update(task['id'],state='PENDING',run_at=time.time()+backoff,retries=retries,data=json.dumps(payload),error=str(exc));return {'status':'RETRYING','error':str(exc),'retry':retries,'backoff':backoff}
            store.task_update(task['id'],state='FAILED',data=json.dumps(payload),error=str(exc),retries=retries);return {'status':'FAILURE','error':str(exc),'retries':retries}
    jobs.run_one=run_one

    def atomic_pull(device_id,limit=20):
        limit=max(1,min(int(limit),100))
        if getattr(store,'_backend',None):
            with store._backend.conn() as c:
                rows=c.execute("SELECT * FROM commands WHERE device_id=%s AND status='PENDING' ORDER BY created LIMIT %s FOR UPDATE SKIP LOCKED",(device_id,limit)).fetchall();out=[];now=time.time()
                for row in rows:
                    r=dict(row);c.execute('UPDATE commands SET status=%s,updated=%s WHERE id=%s AND status=%s',('DELIVERED',now,r['id'],'PENDING'));r['payload']=json.loads(r['payload']);out.append(r)
                return out
        with store.lock,store.conn() as c:
            c.execute('BEGIN IMMEDIATE');rows=[dict(r) for r in c.execute("SELECT * FROM commands WHERE device_id=? AND status='PENDING' ORDER BY created LIMIT ?",(device_id,limit)).fetchall()];now=time.time();out=[]
            for r in rows:
                cur=c.execute('UPDATE commands SET status=?,updated=? WHERE id=? AND status=?',('DELIVERED',now,r['id'],'PENDING'))
                if cur.rowcount==1:r['payload']=json.loads(r['payload']);out.append(r)
            c.commit();return out
    store.pull_commands=atomic_pull

    def atomic_result(command_id,status,result,device_id=None):
        if device_id:
            if getattr(store,'_backend',None):
                with store._backend.conn() as c:
                    cur=c.execute('UPDATE commands SET status=%s,result=%s,updated=%s WHERE id=%s AND device_id=%s',(status,json.dumps(result),time.time(),command_id,device_id));
                    if cur.rowcount!=1:raise PermissionError('command does not belong to authenticated device')
                    return None
            with store.lock,store.conn() as c:
                cur=c.execute('UPDATE commands SET status=?,result=?,updated=? WHERE id=? AND device_id=?',(status,json.dumps(result),time.time(),command_id,device_id));
                if cur.rowcount!=1:raise PermissionError('command does not belong to authenticated device')
                return None
        return store._backend.command_result(command_id,status,result,device_id) if getattr(store,'_backend',None) else store.command_result.__wrapped__(command_id,status,result) if hasattr(store.command_result,'__wrapped__') else None
    # Preserve a direct non-device path for internal callers by binding the current Store method only when needed.
    original_result=store.command_result
    def result_wrapper(command_id,status,result,device_id=None):
        if device_id is not None:return atomic_result(command_id,status,result,device_id)
        return original_result(command_id,status,result)
    store.command_result=result_wrapper

    return {'status':'INSTALLED'}


def _json(value):
    try:return json.loads(value or '{}')
    except Exception:return {}
