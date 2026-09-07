from __future__ import annotations
import json,time

def attach(store):
    def restore_runtime_state(state):
        if not isinstance(state,dict):
            raise ValueError('invalid recovery state')
        restored={'tasks':0,'devices':0,'entities':0,'relations':0,'facts':0}
        tasks=state.get('tasks') or []
        for task in tasks:
            tid=str(task.get('id',''))
            if not tid:
                continue
            existing=store.row('SELECT id FROM tasks WHERE id=?',(tid,))
            data=task.get('data') if isinstance(task.get('data'),str) else json.dumps(task.get('data') or {})
            fields={
                'objective':task.get('objective',''),
                'state':task.get('state','PENDING'),
                'priority':int(task.get('priority') or 0),
                'handler':task.get('handler',''),
                'data':data,
                'run_at':task.get('run_at'),
                'interval_sec':task.get('interval_sec'),
                'retries':int(task.get('retries') or 0),
                'error':task.get('error','') or '',
            }
            if existing:
                fields['updated']=time.time();store.task_update(tid,**fields)
            else:
                store.exec('INSERT INTO tasks(id,objective,state,priority,handler,data,run_at,interval_sec,retries,created,updated,error) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(
                    tid,fields['objective'],fields['state'],fields['priority'],fields['handler'],fields['data'],fields['run_at'],fields['interval_sec'],fields['retries'],float(task.get('created') or time.time()),time.time(),fields['error']))
            restored['tasks']+=1
        for device in state.get('devices') or []:
            did=str(device.get('id',''))
            if not did:continue
            existing=store.row('SELECT id FROM devices WHERE id=?',(did,))
            data=device.get('data') if isinstance(device.get('data'),str) else json.dumps(device.get('data') or {})
            if existing:
                store.exec('UPDATE devices SET name=?,platform=?,last_seen=?,status=?,data=? WHERE id=?',(device.get('name',''),device.get('platform',''),device.get('last_seen'),device.get('status','STALE'),data,did))
            else:
                store.exec('INSERT INTO devices(id,name,platform,public_key,token_hash,last_seen,status,data) VALUES(?,?,?,?,?,?,?,?)',(did,device.get('name',''),device.get('platform',''),'','',device.get('last_seen'),device.get('status','STALE'),data))
            restored['devices']+=1
        world=state.get('world') or {}
        for entity in world.get('entities') or []:
            eid=str(entity.get('id',''))
            if not eid:continue
            raw=entity.get('data')
            data=json.loads(raw) if isinstance(raw,str) else (raw or {})
            store.entity(eid,entity.get('kind',''),entity.get('name',''),data);restored['entities']+=1
        for relation in world.get('relations') or []:
            subject=relation.get('subject');predicate=relation.get('predicate');obj=relation.get('object')
            if subject is None or predicate is None or obj is None:continue
            store.relation(subject,predicate,obj,float(relation.get('confidence') or 0),relation.get('source','recovery'));restored['relations']+=1
        for fact in state.get('facts') or world.get('facts') or []:
            statement=fact.get('statement')
            if not statement:continue
            store.fact(statement,fact.get('source','recovery'),fact.get('url',''),float(fact.get('confidence') or .5),fact.get('metadata') or {});restored['facts']+=1
        return restored
    store.restore_runtime_state=restore_runtime_state
    return store
