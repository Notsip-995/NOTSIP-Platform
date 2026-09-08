from __future__ import annotations
import secrets,hashlib
from .actor_context import current_actor
class Pairing:
    def __init__(self,store):self.store=store
    def create_code(self,actor=None):
        owner=str(actor or current_actor()).strip() or 'primary-user'
        if hasattr(self.store,'create_pair_code_for_actor'):return self.store.create_pair_code_for_actor(owner)
        code=self.store.create_pair_code();setattr(self, '_pairing_owner_'+code, owner);return code
    def consume(self,code,device_id,name,platform,public_key='',actor=None):
        owner=str(actor or current_actor()).strip() or 'primary-user'
        if not self.store.consume_pair_code(code):return None
        token=secrets.token_urlsafe(32)
        try:self.store.pair_device(device_id,name,platform,public_key,token,owner=owner)
        except Exception:
            return None
        return token
