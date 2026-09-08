from notsip.actor_context import set_actor,reset_actor
from notsip.account_store import AccountStore


def test_active_account_keys_are_actor_specific(tmp_path):
    class Secrets:
        def __init__(self):self.d={}
        def get(self,k,default=None):return self.d.get(k,default)
        def set(self,k,v):self.d[k]=v
        def delete(self,k):self.d.pop(k,None)
    from notsip.product_routes import _active_account_key
    secrets=Secrets();accounts=AccountStore(secrets)
    ta=set_actor('issuer:a')
    try:
        a=accounts.upsert('google','sub-a','a@example.com');secrets.set(_active_account_key(),a['id']);assert secrets.get(_active_account_key())==a['id']
    finally:reset_actor(ta)
    tb=set_actor('issuer:b')
    try:
        assert secrets.get(_active_account_key()) is None
        b=accounts.upsert('google','sub-b','b@example.com');secrets.set(_active_account_key(),b['id']);assert secrets.get(_active_account_key())==b['id']
    finally:reset_actor(tb)
