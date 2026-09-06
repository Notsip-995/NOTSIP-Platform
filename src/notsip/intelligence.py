from __future__ import annotations
import json, re, time
from collections import Counter

class Intelligence:
    """Model-independent reasoning support: planning, evidence fusion, contradictions and proactive triggers."""
    def __init__(self,store,world): self.store=store; self.world=world
    def plan(self,objective):
        intent=objective.strip(); steps=[]
        if not intent:return {'objective':'','steps':[]}
        steps.append({'id':1,'action':'understand','description':'Extract goal, constraints, dependencies and success criteria.','state':'READY'})
        steps.append({'id':2,'action':'gather','description':'Retrieve relevant memory, world entities and verified external evidence.','state':'PENDING'})
        steps.append({'id':3,'action':'execute','description':'Choose the minimum-risk authorized actions required for the goal.','state':'PENDING'})
        steps.append({'id':4,'action':'verify','description':'Check tool results and external state; do not infer success from intent.','state':'PENDING'})
        steps.append({'id':5,'action':'record','description':'Persist durable facts, outcomes and unresolved questions with provenance.','state':'PENDING'})
        return {'objective':intent,'steps':steps,'created_at':time.time()}
    def corroborate(self,query):
        facts=self.store.facts(100); matches=[f for f in facts if query.lower() in f.get('statement','').lower() or query.lower() in (f.get('url') or '').lower()]
        by_statement=Counter(x['statement'] for x in matches); return [{'statement':s,'support':n,'sources':[x.get('source') for x in matches if x['statement']==s]} for s,n in by_statement.most_common()]
    def contradictions(self,entity=None):
        rel=self.world.snapshot().get('relations',[]); out=[]
        by_key={}
        for r in rel:
            if entity and entity not in (r.get('subject',''),r.get('object','')):continue
            by_key.setdefault((r.get('subject'),r.get('predicate')),[]).append(r)
        for k,rows in by_key.items():
            objs={r.get('object') for r in rows}
            if len(objs)>1: out.append({'subject':k[0],'predicate':k[1],'alternatives':list(objs),'evidence':rows})
        return out
    def trigger_candidates(self):
        memories=self.store.memories('primary-user','',100)
        return [{'type':'follow_up','reason':'high_weight_unresolved_memory','memory':m['content']} for m in memories if float(m.get('weight',0))>=.9 and any(w in m['content'].lower() for w in ('todo','remember to','follow up','deadline'))][:20]
