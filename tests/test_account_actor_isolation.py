from notsip.account_store import AccountStore
from notsip.actor_context import set_actor,reset_actor


def test_same_provider_subject_is_separate_per_actor(tmp_path):
    class Secrets:
        def __init__(self):self.d={}
        def get(self,k,default=None):return self.d.get(k,default)
        def set(self,k,v):self.d[k]=v
    accounts=AccountStore(Secrets())
    ta=set_actor('issuer:a')
    try:a=accounts.upsert('google','subject-1','a@example.com')
    finally:reset_actor(ta)
    tb=set_actor('issuer:b')
    try:b=accounts.upsert('google','subject-1','b@example.com')
    finally:reset_actor(tb)
    assert a['id']!=b['id']
    ta=set_actor('issuer:a')
    try:
        assert accounts.list()[0]['email']=='a@example.com'
        assert accounts.get(b['id']) is None
    finally:reset_actor(ta)
    tb=set_actor('issuer:b')
    try:
        assert accounts.list()[0]['email']=='b@example.com'
        assert accounts.get(a['id']) is None
    finally:reset_actor(tb)
