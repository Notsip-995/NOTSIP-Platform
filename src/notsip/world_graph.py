from __future__ import annotations
from dataclasses import dataclass
@dataclass
class Entity:
    id:str; kind:str; name:str; data:dict
@dataclass
class Relation:
    source:str; relation:str; target:str; confidence:float=.8
class WorldGraph:
    def __init__(self,store): self.store=store
    def upsert(self,e:Entity): self.store.upsert_entity(e.id,e.kind,e.name,e.data); return e.__dict__
    def relate(self,r:Relation): self.store.upsert_relation(r.source,r.relation,r.target,r.confidence); return r.__dict__
    def snapshot(self): return {'entities':self.store.list_entities(),'relations':self.store.list_relations()}
