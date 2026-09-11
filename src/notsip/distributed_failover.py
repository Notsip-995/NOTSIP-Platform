from __future__ import annotations
import json,time
from .events import Event


def attach(events,store):
    async def recover(event):
        stale={str(n.get('id')) for n in (event.payload.get('nodes') or []) if n.get('id')}
        if not stale:return
        actions=[]
        for task in store.tasks():
            if task.get('state') not in {'PENDING','RUNNING'}:continue
            try:data=json.loads(task.get('data') or '{}')
            except Exception:data={}
            target=str(data.get('target_node') or data.get('node_id') or '').strip()
            if target not in stale or data.get('failover_handled'):continue
            now=time.time();data.update({'failover_handled':True,'failed_node':target,'failover_at':now})
            if task.get('state')=='PENDING':
                data.pop('target_node',None);data.pop('node_id',None);data['redispatched_without_node']=True
                store.task_update(task['id'],state='PENDING',run_at=now,data=json.dumps(data),error='target node became stale; re-queued for available execution')
                actions.append({'task_id':task['id'],'node':target,'action':'REDISPATCHED'})
            else:
                store.task_update(task['id'],state='UNKNOWN',data=json.dumps(data),error='target node became stale while task was running; manual reconciliation required')
                actions.append({'task_id':task['id'],'node':target,'action':'MARKED_UNKNOWN'})
        if actions:await events.publish(Event('tasks.failover',{'nodes':sorted(stale),'actions':actions},'distributed-failover'))
    events.on('nodes.stale',recover)
    return recover
