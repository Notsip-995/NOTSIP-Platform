from __future__ import annotations
from dataclasses import dataclass
@dataclass
class WorldModel:
    store: object
    def upsert(self,eid,kind,name,data): self.store.upsert_entity(eid,kind,name,data)
    def snapshot(self):
        return {'people':self.store.list_entities('person'),'projects':self.store.list_entities('project'),'devices':self.store.list_entities('device'),'places':self.store.list_entities('place'),'events':self.store.list_entities('event')}
