from __future__ import annotations
import secrets
from .actor_context import current_actor
class Pairing:
    """Android pairing facade over the canonical actor-bound Store methods.

    Actor binding is enforced by Store.pair_device(owner=...) and by the
    pairing hardening layer, which records the creating actor for each code.
    """
    def __init__(self,store):self.store=store
    def create_code(self,actor=None):
        return self.store.create_pair_code()
    def consume(self,code,device_id,name,platform,public_key='',actor=None):
        if not self.store.consume_pair_code(code):return None
        token=secrets.token_urlsafe(32)
        self.store.pair_device(device_id,name,platform,public_key,token,owner=str(actor or current_actor()).strip() or 'primary-user')
        return token
