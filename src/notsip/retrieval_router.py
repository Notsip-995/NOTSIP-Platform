from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class RetrievalPlan:
    sources: tuple[str,...]
    public_web: bool
    rationale: str

class RetrievalRouter:
    """Deterministic source selection that prefers private/system evidence and adds public sources only when intent calls for them."""
    PRIVATE=('personal_memory','conversations','email','calendar','documents','messages','contacts')
    PUBLIC=('web','news','public_data','weather')
    SYSTEM=('system_telemetry','system_logs','processes','network','disk','device_status')
    ANALYTICAL=('analytical_db','enterprise_db','financial_db')
    def plan(self, query: str) -> RetrievalPlan:
        q=' '.join(str(query or '').lower().split())
        if not q:return RetrievalPlan((),False,'empty query')
        sources=[]
        private_markers=('my ','i ','me ','promise','promised','meeting','calendar','email','message','document','file','project','contact','schedule','last week','yesterday','tomorrow','spent','purchase','invoice')
        system_markers=('server','cpu','memory','disk','network','slow','latency','process','performance','error','diagnostic','telemetry','device','power','temperature')
        news_markers=('news','happening','today','latest','recent','headline','report')
        weather_markers=('weather','forecast','temperature','rain','wind','humidity','storm')
        financial_markers=('spent','spend','budget','revenue','expense','invoice','transaction','financial','money')
        enterprise_markers=('enterprise','business database','erp','crm','inventory','sales database')
        analytical_markers=('analysis','analytics','historical','trend','dataset','statistics')
        if any(m in q for m in system_markers):sources.extend(self.SYSTEM)
        if any(m in q for m in private_markers):sources.extend(self.PRIVATE)
        if any(m in q for m in financial_markers):sources.append('financial_db')
        if any(m in q for m in enterprise_markers):sources.append('enterprise_db')
        if any(m in q for m in analytical_markers):sources.append('analytical_db')
        if any(m in q for m in news_markers):sources.extend(('news','web','public_data'))
        if any(m in q for m in weather_markers):sources.append('weather')
        public=bool(any(s in sources for s in self.PUBLIC))
        if not sources:sources.extend(('personal_memory','documents','web'))
        seen=[]
        for source in sources:
            if source not in seen:seen.append(source)
        # Personal commitments stay private-first and do not leak into public search by default.
        if any(m in q for m in ('what did i promise','what have i promised','what did i tell','what did i agree')):
            seen=[s for s in seen if s not in self.PUBLIC]+[s for s in seen if s in self.PUBLIC]
            public=False
        return RetrievalPlan(tuple(seen),public,'selected sources from query semantics; sensitive personal questions prefer private sources')
