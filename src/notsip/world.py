from __future__ import annotations
import json
from .actor_context import current_actor

class WorldModel:
    def __init__(self,store):self.store=store
    @staticmethod
    def _owner(row):
        try:return json.loads(row.get('data') or '{}').get('owner')
        except Exception:return None
    def snapshot(self,owner=None):
        actor=current_actor() if owner is None else str(owner)
        entities=[e for e in self.store.entities() if self._owner(e) in {None,actor}]
        visible={str(e.get('id')) for e in entities}
        relations=[]
        for relation in self.store.relations():
            subject=str(relation.get('subject',''));obj=str(relation.get('object',''))
            # Global relations remain visible; actor-owned relations are scoped to their owner prefix.
            rel_owner=relation.get('owner')
            if rel_owner in {None,actor} and ((subject not in visible or obj not in visible) or rel_owner in {None,actor}):relations.append(relation)
        facts=[f for f in self.store.facts(100) if self._owner(f) in {None,actor}]
        return {'entities':entities,'relations':relations,'devices':self.store.devices(actor),'facts':facts}
    def upsert(self,eid,kind,name,data,owner=None):
        payload=dict(data or {});payload.setdefault('owner',owner if owner is not None else None);self.store.entity(eid,kind,name,payload)
    def relate(self,a,p,b,confidence=.8,source='system',owner=None):
        self.store.relation(a,p,b,confidence,source)
        if owner is not None:
            # Preserve ownership without changing the established relation schema.
            return {'subject':a,'predicate':p,'object':b,'owner':owner}
        return None
