from __future__ import annotations
from dataclasses import asdict, dataclass

@dataclass(frozen=True)
class Uncertainty:
    status:str
    confidence:float
    reasons:list[str]
    action:str

class UncertaintyEngine:
    def evaluate(self, *, evidence_count=0, confidence=0.0, conflicts=0, required_fields=None, missing_fields=None, authorized=True, reversible=True):
        reasons=[];confidence=max(0.0,min(1.0,float(confidence)))
        if not authorized:reasons.append('authorization missing')
        if conflicts:reasons.append(f'{int(conflicts)} evidence conflict(s) unresolved')
        if missing_fields:reasons.append('missing information: '+', '.join(map(str,missing_fields)))
        if int(evidence_count)<=0:reasons.append('no supporting evidence available')
        if reasons:
            status='BLOCKED' if not authorized else 'UNCERTAIN';action='request authorization' if not authorized else 'gather independent evidence or ask for clarification'
        elif confidence<0.5:
            status='LOW_CONFIDENCE';action='gather stronger evidence before acting'
        elif confidence<0.8:
            status='MODERATE_CONFIDENCE';action='verify critical facts before irreversible action'
        else:
            status='HIGH_CONFIDENCE';action='proceed only within authorized and reversible boundaries' if reversible else 'obtain explicit confirmation before irreversible action'
        return Uncertainty(status,confidence,reasons,action)
    def from_fusion(self,fusion_result):
        claims=fusion_result.get('claims') or [];best=claims[0] if claims else {};return self.evaluate(evidence_count=sum(int(x.get('support',0)) for x in claims),confidence=float(best.get('confidence',0)),conflicts=len(fusion_result.get('conflicts') or []))
