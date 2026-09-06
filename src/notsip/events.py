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
        for fn in self.handlers.get(event.type,[]):
            result=fn(event)
            if asyncio.iscoroutine(result): await result
        for q in list(self.subscribers): await q.put(event)
    def subscribe(self): q=asyncio.Queue(); self.subscribers.append(q); return q
    def unsubscribe(self,q):
        if q in self.subscribers: self.subscribers.remove(q)
