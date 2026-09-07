from dataclasses import dataclass,field
from datetime import datetime,timezone
import asyncio
@dataclass(slots=True)
class Event:
    type:str; payload:dict; source:str='internal'; timestamp:str=field(default_factory=lambda:datetime.now(timezone.utc).isoformat())
class EventBus:
    def __init__(self): self.handlers={}; self.subscribers=[]
    def on(self,event_type,fn): self.handlers.setdefault(event_type,[]).append(fn)
    async def publish(self,event):
        errors=[]
        for fn in list(self.handlers.get(event.type,[])):
            try:
                result=fn(event)
                if asyncio.iscoroutine(result): await result
            except Exception as exc:
                errors.append({'kind':'handler','error':str(exc),'event':event.type})
        for q in list(self.subscribers):
            try: await q.put(event)
            except Exception as exc: errors.append({'kind':'subscriber','error':str(exc),'event':event.type})
        return errors
    def subscribe(self): q=asyncio.Queue(); self.subscribers.append(q); return q
    def unsubscribe(self,q):
        if q in self.subscribers: self.subscribers.remove(q)
