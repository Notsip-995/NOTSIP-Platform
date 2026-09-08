from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class RetrievalPlan:
    sources: tuple[str,...]
    public_web: bool
    rationale: str

class RetrievalRouter:
    """Deterministic first-pass source selection; models may refine, but cannot erase privacy boundaries."""
    PRIVATE=('personal_memory','conversations','email','calendar','documents')
    PUBLIC=('web','news','public_data')
    SYSTEM=('system_telemetry','system_logs','processes','network','disk')

    def plan(self, query: str) -> RetrievalPlan:
        q=' '.join(str(query or '').lower().split())
        if not q:return RetrievalPlan((),False,'empty query')
        sources=[]
        private_markers=('my ','i ','me ','promise','promised','meeting','calendar','email','message','document','file','project','contact','schedule','last week','yesterday','tomorrow')
        system_markers=('server','cpu','memory','disk','network','slow','latency','process','performance','error','diagnostic','telemetry')
        public_markers=('latest','today','news','happening','current','public','recent','who is','what happened')
        if any(m in q for m in system_markers):sources.extend(self.SYSTEM)
        if any(m in q for m in private_markers):sources.extend(self.PRIVATE)
        public=any(m in q for m in public_markers)
        if public:sources.extend(self.PUBLIC)
        if not sources:sources.extend(('personal_memory','documents','web'))
        seen=[]
        for source in sources:
            if source not in seen:seen.append(source)
        # Queries explicitly about the user's commitments remain private-first.
        if any(m in q for m in ('what did i promise','what have i promised','what did i tell','what did i agree')):
            seen=[s for s in seen if s not in self.PUBLIC]+[s for s in seen if s in self.PUBLIC]
            public=False
        return RetrievalPlan(tuple(seen),public,'selected sources from query semantics; public web is opt-in from current/public intent')
