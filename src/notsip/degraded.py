from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass
class ServiceState:
    name: str
    available: bool
    reason: str=''
    checked_at: str=''

class DegradedMode:
    def __init__(self): self.states={}
    def set(self,name,available,reason=''):
        self.states[name]=ServiceState(name,available,reason,datetime.now(timezone.utc).isoformat())
    def snapshot(self): return {k:v.__dict__ for k,v in self.states.items()}
