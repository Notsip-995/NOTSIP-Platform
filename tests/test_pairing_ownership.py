from notsip.security import SecretStore
from notsip.store import Store
from notsip.actor_context import set_actor,reset_actor
from notsip.pairing_hardening import PairIn


def test_pairing_code_owner_is_enforced(tmp_path):
    store=Store(tmp_path);secrets=SecretStore(tmp_path);code=store.create_pair_code();secrets.set('pairing:owner:'+code,{'actor':'issuer:user-a'})
    tb=set_actor('issuer:user-b')
    try:
        record=secrets.get('pairing:owner:'+code)
        assert record['actor']!='issuer:user-b'
    finally:reset_actor(tb)
    ta=set_actor('issuer:user-a')
    try:
        assert secrets.get('pairing:owner:'+code)['actor']=='issuer:user-a'
        assert store.consume_pair_code(code) is True
        assert store.consume_pair_code(code) is False
    finally:reset_actor(ta)
