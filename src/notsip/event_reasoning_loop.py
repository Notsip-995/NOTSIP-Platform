from __future__ import annotations
import hashlib,json
from .event_priority import EventPriorityEngine
from .task_model import TaskRecord

class EventReasoningLoop:
    """Bridge qualifying observations into durable review tasks without granting action authority."""
    TRIGGERS={'perception.observed','health.warning','maintenance.prediction','nodes.stale','perception.error'}
    def __init__(self,events,scheduler,priority=None):self.events=events;self.scheduler=scheduler;self.priority=priority or EventPriorityEngine()
    def attach(self):
        for event_type in self.TRIGGERS:self.events.on(event_type,self.handle)
        return self
    def _payload_score(self,payload):return float(payload.get('importance',.65)),float(payload.get('urgency',.35)),float(payload.get('relevance',.75))
    def handle(self,event):
        payload=event.payload or {};importance,urgency,relevance=self._payload_score(payload);decision=self.priority.classify(importance=importance,urgency=urgency,relevance=relevance,event_type=event.type)
        if decision.priority.value<3:return {'status':'IGNORED','priority':decision.priority.name}
        digest=hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()[:20]
        objective=f"Review {event.type} and determine whether any authorized follow-up is required. Evidence: {json.dumps(payload,default=str)[:3000]}"
        task=TaskRecord(objective=objective,requester='system',context={'trigger_event':event.type,'event_timestamp':event.timestamp,'evidence':payload},priority=int(decision.priority),constraints=['review only','no external action without separate authorization'],required_tools=['route_retrieval','uncertainty_assess'],permissions=[],subtasks=[],state='PENDING',result={},verification={'required':True,'verified':False})
        task_id=self.scheduler.create(objective,handler='agent',delay=0,priority=int(decision.priority),data=task.to_dict(),idempotency_key=f"event-review:{event.type}:{digest}")
        return {'status':'CREATED','task_id':task_id,'priority':decision.priority.name,'interrupt':decision.interrupt}
