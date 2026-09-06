from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4
@dataclass
class Confirmation:
    id:str; action:str; reason:str; created_at:str; status:str='PENDING'
class ConfirmationEngine:
    def __init__(self): self.pending={}
    def request(self,action,reason):
        c=Confirmation(str(uuid4()),action,reason,datetime.now(timezone.utc).isoformat()); self.pending[c.id]=c; return c.__dict__
    def decide(self,cid,approved):
        c=self.pending.get(cid)
        if not c: return None
        c.status='APPROVED' if approved else 'REJECTED'; return c.__dict__
    def list(self): return [c.__dict__ for c in self.pending.values() if c.status=='PENDING']
