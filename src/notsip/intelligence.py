import json,re,time
from collections import defaultdict
from .actor_context import current_actor
_PUBLIC_SOURCES={'brave','public','web','system'}

class Intelligence:
    """Model-independent planning, evidence fusion, contradictions and proactive triggers."""
    def __init__(self,store,world): self.store=store; self.world=world
    @staticmethod
    def _fact_allowed(store,fact,actor):
        if actor=='primary-user':return True
        source=str(fact.get('source') or '').lower()
        if source in _PUBLIC_SOURCES:return True
        metadata=fact.get('metadata') or {}
        if isinstance(metadata,str):
            try:metadata=json.loads(metadata)
            except json.JSONDecodeError:metadata={}
        if str(metadata.get('actor') or '')==actor:return True
        device_id=str(metadata.get('device_id') or '')
        return bool(device_id and store.device_owned_by(device_id,actor))
    def plan(self,objective):
        intent=objective.strip()
        if not intent:return {'objective':'','steps':[]}
        return {'objective':intent,'steps':[
            {'id':1,'action':'understand','description':'Extract goal, constraints, dependencies and success criteria.','state':'READY'},
            {'id':2,'action':'gather','description':'Retrieve relevant memory, world entities and verified external evidence.','state':'PENDING'},
            {'id':3,'action':'execute','description':'Choose the minimum-risk authorized actions required for the goal.','state':'PENDING'},
            {'id':4,'action':'verify','description':'Check tool results and external state; do not infer success from intent.','state':'PENDING'},
            {'id':5,'action':'record','description':'Persist durable facts, outcomes and unresolved questions with provenance.','state':'PENDING'}], 'created_at':time.time()}
    def corroborate(self,query):
        q=query.strip().lower()
        if not q:return []
        actor=current_actor();groups=defaultdict(list)
        for fact in self.store.facts(500):
            if not self._fact_allowed(self.store,fact,actor):continue
            statement=str(fact.get('statement',''));url=str(fact.get('url') or '')
            if q not in statement.lower() and q not in url.lower():continue
            normalized=re.sub(r'\s+',' ',statement.strip()).casefold();groups[normalized].append(fact)
        out=[];now=time.time()
        for rows in groups.values():
            sources=[];best=0.0;fresh=0.0
            for row in rows:
                src=str(row.get('source') or 'unknown')
                if src not in sources:sources.append(src)
                best=max(best,float(row.get('confidence') or 0.0));fresh=max(fresh,float(row.get('retrieved') or 0.0))
            age=None if not fresh else max(0.0,(now-fresh)/86400)
            out.append({'statement':rows[0].get('statement',''),'support':len(rows),'independent_sources':len(sources),'sources':sources,'best_source_confidence':round(best,4),'corroboration_score':round(min(1.0,.5+.2*max(0,len(sources)-1)),4),'freshest_retrieved':fresh,'age_days':None if age is None else round(age,3),'evidence':rows})
        return sorted(out,key=lambda x:(x['independent_sources'],x['best_source_confidence'],x['freshest_retrieved']),reverse=True)
    def contradictions(self,entity=None):
        rel=self.world.snapshot().get('relations',[]);by_key=defaultdict(list)
        for r in rel:
            if entity and entity not in (r.get('subject',''),r.get('object','')):continue
            by_key[(r.get('subject'),r.get('predicate'))].append(r)
        return [{'subject':k[0],'predicate':k[1],'alternatives':sorted({r.get('object') for r in rows}),'evidence':rows} for k,rows in by_key.items() if len({r.get('object') for r in rows})>1]
    def trigger_candidates(self,actor=None):
        owner=str(actor or current_actor()).strip() or 'primary-user'
        memories=self.store.memories(owner,'',100)
        return [{'type':'follow_up','reason':'high_weight_unresolved_memory','memory':m['content'],'actor':owner} for m in memories if float(m.get('weight',0))>=.9 and any(w in m['content'].lower() for w in ('todo','remember to','follow up','deadline'))][:20]
