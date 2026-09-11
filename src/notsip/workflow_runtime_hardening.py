from __future__ import annotations
import copy,json,time
from .system_services import WorkflowEngine


class DurableWorkflowEngine(WorkflowEngine):
    """Persist completed workflow steps so a scheduler retry resumes instead of replaying them."""

    async def run_task(self, task):
        data=task.get('data') or {}
        if isinstance(data,str):data=json.loads(data or '{}')
        steps=data.get('steps') or []
        if not isinstance(steps,list) or not steps:return {'status':'FAILURE','error':'workflow steps required','steps':[]}
        if len(steps)>self.MAX_STEPS:return {'status':'FAILURE','error':f'workflow too large; maximum is {self.MAX_STEPS} steps','steps':[]}
        ids=[];by_id={}
        for index,step in enumerate(steps):
            if not isinstance(step,dict):return {'status':'FAILURE','error':f'step {index} must be an object','steps':[]}
            sid=str(step.get('id') or index+1)
            if sid in by_id:return {'status':'FAILURE','error':f'duplicate step id: {sid}','steps':[]}
            ids.append(sid);by_id[sid]=step
        results=list(data.get('step_results') or [])
        result_map={str(r.get('id')):r for r in results if r.get('id') is not None}
        if set(result_map)-set(ids):return {'status':'FAILURE','error':'workflow contains an unknown persisted step result','steps':results}
        for sid in ids:
            if sid in result_map:continue
            step=by_id[sid];deps=[str(x) for x in (step.get('depends_on',step.get('requires',[])) or [])]
            if any(dep not in by_id for dep in deps):
                return {'status':'FAILURE','error':f'unknown dependency for step {sid}','steps':results}
            if any(dep not in result_map for dep in deps):continue
            dep_results=[result_map[d] for d in deps];failed_dep=any(r.get('status') not in {'SUCCESS','DEGRADED','SKIPPED'} for r in dep_results)
            condition=str(step.get('condition','always')).lower()
            if condition in {'on_success','success'} and failed_dep:
                current={'id':sid,'status':'SKIPPED','reason':'dependency failed'}
            elif condition in {'on_failure','failure'} and not failed_dep:
                current={'id':sid,'status':'SKIPPED','reason':'failure condition not met'}
            elif condition in {'on_unknown','unknown'} and not any(r.get('status')=='UNKNOWN' for r in dep_results):
                current={'id':sid,'status':'SKIPPED','reason':'unknown condition not met'}
            else:
                step_copy=copy.deepcopy(step);step_copy.pop('depends_on',None);step_copy.pop('requires',None);step_copy.pop('condition',None)
                result=await self.run([step_copy]);current={'id':sid,'status':str(result.get('steps',[{}])[0].get('status','UNKNOWN')) if isinstance(result,dict) and result.get('steps') else str(result.get('status','UNKNOWN')),'result':result}
            result_map[sid]=current;results.append(current);data['step_results']=results;data['current_step']=len([x for x in ids if x in result_map]);data['state']=current['status'];data['verification']=current.get('result',{}).get('verification',{}) if isinstance(current.get('result'),dict) else {}
            accepted=current['status'] in {'SUCCESS','DEGRADED','SKIPPED'}
            if not accepted:
                final_status='UNKNOWN' if current['status']=='UNKNOWN' else 'PARTIAL_SUCCESS';data['state']=final_status;self.store.task_update(task['id'],state=final_status,data=json.dumps(data),error=str(current.get('result',{}).get('error','')) if isinstance(current.get('result'),dict) else '')
                return {'status':final_status,'steps':results}
            remaining=[x for x in ids if x not in result_map]
            if remaining:
                self.store.task_update(task['id'],state='PENDING',run_at=time.time(),data=json.dumps(data),error='')
                return {'status':'CONTINUE','run_at':time.time(),'steps':results,'next_step':remaining[0]}
        data['current_step']=len(ids);data['state']='SUCCESS';data['completed_at']=time.time();self.store.task_update(task['id'],state='COMPLETED',data=json.dumps(data),error='')
        return {'status':'SUCCESS','steps':results}


def attach(jobs, store, agent):
    engine=DurableWorkflowEngine(store,agent)

    async def workflow_handler(task):
        return await engine.run_task(task)

    jobs.register('workflow',workflow_handler)
    return engine
