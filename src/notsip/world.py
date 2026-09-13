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
            except (TypeError,ValueError):continue
        return None
    @staticmethod
    def _relation_owner(row):
        source=str(row.get('source') or '')
        if source.startswith('actor:'):
            # Legacy relations were created before relation ownership existed.
            owner,_,_source=source.partition('|')
            return owner[6:].strip() or 'primary-user'
        return 'primary-user'
    @staticmethod
    def _as_json(row,field,default=None):
        try:value=json.loads(row.get(field) or '{}') if isinstance(row.get(field),str) else row.get(field) or {}
        except (TypeError,ValueError):value=default or {}
        return value if isinstance(value,dict) else default or {}
    def snapshot(self,owner=None):
        actor=current_actor() if owner is None else str(owner)
        all_entities=self.store.entities();hidden={str(e.get('id')) for e in all_entities if self._owner(e) not in {None,actor}}
        entities=[]
        for e in all_entities:
            if str(e.get('id')) in hidden:continue
            out=dict(e);out['data']=self._as_json(out,'data');entities.append(out)
        relations=[]
        for relation in self.store.relations():
            if self._relation_owner(relation)!=actor:continue
            if str(relation.get('subject','')) in hidden or str(relation.get('object','')) in hidden:continue
            out=dict(relation);out['metadata']=self._as_json(out,'metadata');relations.append(out)
        facts=[f for f in self.store.facts(100) if self._owner(f) in {None,actor}]
        return {'entities':entities,'relations':relations,'devices':self.store.devices(actor),'facts':facts}
    def upsert(self,eid,kind,name,data,owner=None):
        actor=current_actor() if owner is None else str(owner);payload=dict(data or {});payload['owner']=actor;self.store.entity(eid,kind,name,payload);return {'status':'SUCCESS','id':eid,'owner':actor}
    def relate(self,a,p,b,confidence=.8,source='system',owner=None):
        actor=current_actor() if owner is None else str(owner);provenance=f'actor:{actor}|{source}';self.store.relation(a,p,b,confidence,provenance);return {'subject':a,'predicate':p,'object':b,'owner':actor}
