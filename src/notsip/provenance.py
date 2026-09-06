from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib

@dataclass
class Evidence:
    source: str
    claim: str
    timestamp: str
    confidence: float
    kind: str='fact'
    corroboration: int=1
    def to_dict(self): return asdict(self)

class EvidenceLedger:
    def __init__(self, store): self.store=store
    def record(self, source, claim, confidence=0.8, kind='fact', corroboration=1):
        ev=Evidence(source,claim,datetime.now(timezone.utc).isoformat(),max(0,min(1,confidence)),kind,corroboration)
        self.store.record_evidence(ev.to_dict()); return ev.to_dict()
    @staticmethod
    def fingerprint(text:str)->str: return hashlib.sha256(text.encode('utf-8')).hexdigest()
