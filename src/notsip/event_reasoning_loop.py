from __future__ import annotations
import hashlib,json
from .event_priority import EventPriorityEngine
from .task_model import TaskRecord

class EventReasoningLoop:
    """Turn important observations and opted-in task outcomes into bounded review/replan work."""
    TRIGGERS={'perception.observed','health.warning','maintenance.prediction','nodes.stale','perception.error','task.completed','task.failed'}
    def __init__(self,events,scheduler,priority=None):self.events=events;self.scheduler=scheduler;self.priority=priority or EventPriorityEngine()
    def attach(self):
        for event_type in self.TRIGGERS:self.events.on(event_type,self.handle)
        return self
    def _payload_score(self,payload):return float(payload.get('importance',.65)),float(payload.get('urgency',.35)),float(payload.get('relevance',.75))
    def _event_review(self,event):
        payload=event.payload or {};importance,urgency,relevance=self._payload_score(payload);decision=self.priority.classify(importance=importance,urgency=urgency,relevance=relevance,event_type=event.type)
        if decision.priority.value<3:return {'status':'IGNORED','priority':decision.priority.name}
        digest=hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()[:20]
        objective=f"Review {event.type} and determine whether any authorized follow-up is required. Evidence: {json.dumps(payload,default=str)[:3000]}"
        task=TaskRecord(objective=objective,requester='system',context={'trigger_event':event.type,'event_timestamp':event.timestamp,'evidence':payload},priority=int(decision.priority),constraints=['review only','no external action without separate authorization'],required_tools=['route_retrieval','uncertainty_assess'],permissions=[],subtasks=[],state='PENDING',result={},verification={'required':True,'verified':False})
        task_id=self.scheduler.create(objective,handler='agent',delay=0,priority=int(decision.priority),data=task.to_dict(),idempotency_key=f"event-review:{event.type}:{digest}")
        return {'status':'CREATED','task_id':task_id,'priority':decision.priority.name,'interrupt':decision.interrupt}
    def _task_feedback(self,event):
        payload=event.payload or {};task_data=payload.get('task_data') or {};loop=task_data.get('feedback_loop') or {}
        if loop.get('enabled') is not True or task_data.get('review_only'):return {'status':'IGNORED','reason':'feedback loop not enabled for task'}
        cycle=int(task_data.get('feedback_cycle',0) or 0);maximum=max(1,min(int(loop.get('max_cycles',3) or 3),20))
        if cycle>=maximum:return {'status':'STOPPED','reason':'feedback cycle limit reached','cycle':cycle}
        task_id=str(payload.get('task_id',''));execution_id=str(payload.get('execution_id',''))
        decision='COMPLETED' if event.type=='task.completed' else 'FAILED'
        objective=(f"Evaluate the {decision.lower()} task outcome. Decide exactly one next state: CONTINUE, MODIFY, or STOP. "
                   f"Use the observed result and verification evidence; do not claim success that is not present. Original objective: {payload.get('objective','')}. "
                   f"Observed result: {json.dumps(payload.get('result') if event.type=='task.completed' else {'status':'FAILURE','error':payload.get('error','')},default=str)[:5000]}. "
                   f"Available modification/continuation guidance: {json.dumps(loop.get('guidance',{}),default=str)[:2000]}")
        feedback_context={'feedback_loop':{'enabled':True,'max_cycles':maximum,'guidance':loop.get('guidance',{})},'feedback_evaluation_for':task_id,'feedback_cycle':cycle+1,'observed_event':event.type,'original_task_data':task_data,'review_only':True}
        review=TaskRecord(objective=objective,requester=task_data.get('requester','system'),context={'original_task_id':task_id,'execution_id':execution_id,'event_type':event.type,'observed_result':payload.get('result') or {'status':'FAILURE','error':payload.get('error','')}},priority=int(task_data.get('priority',0) or 0),constraints=['evaluation only','do not execute external actions unless separately authorized','must choose CONTINUE, MODIFY, or STOP'],required_tools=['uncertainty_assess','make_plan'],permissions=[],subtasks=[],state='PENDING',result={},verification={'required':True,'verified':False})
        review_data=review.to_dict();review_data.update(feedback_context);digest=hashlib.sha256(json.dumps({'task_id':task_id,'execution_id':execution_id,'cycle':cycle+1},sort_keys=True).encode()).hexdigest()[:20]
        review_id=self.scheduler.create(objective,handler='agent',delay=0,priority=int(task_data.get('priority',0) or 0),data=review_data,idempotency_key=f"task-feedback:{task_id}:{execution_id}:{cycle+1}:{digest}")
        return {'status':'CREATED','task_id':review_id,'original_task_id':task_id,'cycle':cycle+1,'max_cycles':maximum}
    def handle(self,event):
        if event.type in {'task.completed','task.failed'}:return self._task_feedback(event)
        return self._event_review(event)
