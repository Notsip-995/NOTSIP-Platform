from notsip.actor_context import set_actor, reset_actor
from notsip.memory_service import MemoryService


class Store:
    def __init__(self): self.rows=[]
    def memories(self,uid,q='',limit=20): return [{'content':uid}]
    def rows(self,sql,args=()): return []


def test_memory_service_uses_current_actor_store_identity():
    store=Store();token=set_actor('actor-a')
    try: result=MemoryService(store,'actor-a').snapshot()
    finally: reset_actor(token)
    assert result['items'][0]['content']=='actor-a'
