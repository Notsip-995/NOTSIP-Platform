class WorldModel:
    def __init__(self,store):self.store=store
    def snapshot(self):return {'entities':self.store.entities(),'relations':self.store.relations(),'devices':self.store.devices(),'facts':self.store.facts(50)}
    def upsert(self,eid,kind,name,data):self.store.entity(eid,kind,name,data)
    def relate(self,a,p,b,confidence=.8,source='system'):self.store.relation(a,p,b,confidence,source)
