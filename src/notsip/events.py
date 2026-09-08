from dataclasses import dataclass,field
from datetime import datetime,timezone
import asyncio
@dataclass(slots=True)
class Event:
    type:str;payload:dict;source:str='internal';timestamp:str=field(default_factory=lambda:datetime.now(timezone.utc).isoformat())
class EventBus:
    def __init__(self,subscriber_queue_size=1000):self.handlers={};self.subscribers=[];self.subscriber_queue_size=max(10,int(subscriber_queue_size))
    def on(self,event_type,fn):self.handlers.setdefault(event_type,[]).append(fn)
    async def publish(self,event):
        errors=[]
        for fn in list(self.handlers.get(event.type,[])):
            try:
                result=fn(event)
                if asyncio.iscoroutine(result):await result
            except Exception as exc:errors.append({'kind':'handler','error':str(exc),'event':event.type})
        for q in list(self.subscribers):
            try:q.put_nowait(event)
            except asyncio.QueueFull:errors.append({'kind':'subscriber_overflow','error':'subscriber queue is full; event dropped for slow consumer','event':event.type})
            except Exception as exc:errors.append({'kind':'subscriber','error':str(exc),'event':event.type})
        return errors
    def subscribe(self):q=asyncio.Queue(maxsize=self.subscriber_queue_size);self.subscribers.append(q);return q
    def unsubscribe(self,q):
        if q in self.subscribers:self.subscribers.remove(q)
