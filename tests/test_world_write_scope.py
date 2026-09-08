from notsip.actor_context import set_actor, reset_actor
from notsip.world import WorldModel


class Store:
    def __init__(self): self.entities_seen=[]; self.relations_seen=[]
    def entity(self,*args): self.entities_seen.append(args)
    def relation(self,*args): self.relations_seen.append(args)


def test_world_upsert_binds_current_actor():
    store=Store();world=WorldModel(store);token=set_actor('actor-a')
    try: result=world.upsert('e1','person','Alice',{'role':'owner'})
    finally: reset_actor(token)
    assert result['owner']=='actor-a'
    assert store.entities_seen[0][-1]['owner']=='actor-a'


def test_world_relation_reports_current_actor():
    store=Store();world=WorldModel(store);token=set_actor('actor-b')
    try: result=world.relate('e1','knows','e2')
    finally: reset_actor(token)
    assert result['owner']=='actor-b'
