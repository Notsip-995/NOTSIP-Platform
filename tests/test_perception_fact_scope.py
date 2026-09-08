from types import SimpleNamespace
from notsip.actor_context import set_actor, reset_actor
from notsip.completion_routes import store_fact_if_present


class Store:
    def __init__(self): self.rows=[]
    def fact(self,*args): self.rows.append(args); return 'fact-1'


def test_persisted_perception_fact_is_actor_scoped():
    store=Store();token=set_actor('actor-a')
    try: store_fact_if_present(store,{'observation':'private visual observation'},{'prompt':'describe'})
    finally: reset_actor(token)
    assert store.rows
    metadata=store.rows[0][4]
    assert metadata['actor']=='actor-a'


def test_other_actor_cannot_be_represented_as_owner():
    store=Store();token=set_actor('actor-b')
    try: store_fact_if_present(store,{'observation':'observation-b'},{'prompt':''})
    finally: reset_actor(token)
    assert store.rows[0][4]['actor']=='actor-b'
