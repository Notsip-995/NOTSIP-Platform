from __future__ import annotations
import json
from .actor_context import current_actor

class WorldModel:
    def __init__(self,store):self.store=store
    @staticmethod
    def _owner(row):
        for field in ('data','metadata'):
            try:
                value=json.loads(row.get(field) or '{}')
                if isinstance(value,dict) and value.get('owner') is not None:return str(value.get('owner'))
            except Exception:continue
        return None
    def snapshot(self,owner=None):
        actor=current_actor() if owner is None else str(owner)
        all_entities=self.store.entities();hidden={str(e.get('id')) for e in all_entities if self._owner(e) not in {None,actor}}
        entities=[e for e in all_entities if str(e.get('id')) not in hidden]
        relations=[]
        for relation in self.store.relations():
            if str(relation.get('subject','')) in hidden or str(relation.get('object','')) in hidden:continue
            relations.append(relation)
        facts=[f for f in self.store.facts(100) if self._owner(f) in {None,actor}]
        return {'entities':entities,'relations':relations,'devices':self.store.devices(actor),'facts':facts}
    def upsert(self,eid,kind,name,data,owner=None):
        actor=current_actor() if owner is None else str(owner);payload=dict(data or {});payload['owner']=actor;self.store.entity(eid,kind,name,payload);return {'status':'SUCCESS','id':eid,'owner':actor}
    def relate(self,a,p,b,confidence=.8,source='system',owner=None):
        actor=current_actor() if owner is None else str(owner);self.store.relation(a,p,b,confidence,source);return {'subject':a,'predicate':p,'object':b,'owner':actor}
