from notsip.actor_context import set_actor, reset_actor
from notsip.product_layer import ApprovalStore


def test_approval_pending_is_actor_scoped(tmp_path):
    store=ApprovalStore(tmp_path)
    a=set_actor('actor-a')
    try: store.request('danger','reason',{})
    finally: reset_actor(a)
    b=set_actor('actor-b')
    try:
        assert store.pending()==[]
    finally: reset_actor(b)


def test_approval_decision_cannot_mutate_foreign_actor(tmp_path):
    store=ApprovalStore(tmp_path)
    a=set_actor('actor-a')
    try: item=store.request('danger','reason',{})
    finally: reset_actor(a)
    b=set_actor('actor-b')
    try: assert store.decide(item['id'],True) is None
    finally: reset_actor(b)
    a=set_actor('actor-a')
    try: assert store.pending()[0]['status']=='PENDING'
    finally: reset_actor(a)
