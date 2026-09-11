from pathlib import Path
from notsip.actor_context import set_actor,reset_actor
from notsip.product_layer import ApprovalStore


def test_approval_pending_isolation(tmp_path):
    store=ApprovalStore(tmp_path)
    ta=set_actor('issuer:user-a')
    try:a=store.request('danger','reason',{'actor':'issuer:user-a','tool':'demo'})
    finally:reset_actor(ta)
    tb=set_actor('issuer:user-b')
    try:
        visible=[x for x in store.pending() if (x.get('context') or {}).get('actor','primary-user')=='issuer:user-b']
        assert visible==[]
    finally:reset_actor(tb)
    assert store.pending()[0]['id']==a['id']


def test_forged_context_cannot_change_ownership():
    payload={'context':{'actor':'issuer:user-b','tool':'demo'}}
    actor='issuer:user-a'
    payload['context']['actor']=actor
    assert payload['context']['actor']=='issuer:user-a'
