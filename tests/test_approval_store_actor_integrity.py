import pytest
from notsip.actor_context import reset_actor, set_actor
from notsip.product_layer import ApprovalStore


def test_approval_request_cannot_impersonate_other_actor(tmp_path):
    store = ApprovalStore(tmp_path)
    token = set_actor('actor-a')
    try:
        with pytest.raises(PermissionError, match='authenticated actor'):
            store.request('danger', 'reason', {'actor': 'actor-b'}, actor='actor-b')
        item = store.request('danger', 'reason', {})
        assert item['context']['actor'] == 'actor-a'
    finally:
        reset_actor(token)


def test_approval_pending_cannot_enumerate_other_actor(tmp_path):
    store = ApprovalStore(tmp_path)
    token = set_actor('actor-a')
    try:
        store.request('danger', 'reason', {})
    finally:
        reset_actor(token)
    token = set_actor('actor-b')
    try:
        assert store.pending() == []
        with pytest.raises(PermissionError, match='authenticated actor'):
            store.pending(actor='actor-a')
    finally:
        reset_actor(token)
