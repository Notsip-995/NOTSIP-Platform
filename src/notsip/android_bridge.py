from __future__ import annotations
import secrets
from .actor_context import current_actor
class Pairing:
    def __init__(self,store):self.store=store
    def create_code(self,actor=None):
        owner=str(actor or current_actor()).strip() or 'primary-user'
        creator=getattr(self.store,'create_pair_code_for_actor',None)
        if creator is None:raise RuntimeError('actor-bound pairing is required; legacy pairing store is unsupported')
        return creator(owner)
    def consume(self,code,device_id,name,platform,public_key='',actor=None):
        owner=str(actor or current_actor()).strip() or 'primary-user'
        consumer=getattr(self.store,'consume_pair_code_for_actor',None)
        if consumer is None:raise RuntimeError('actor-bound pairing is required; legacy pairing store is unsupported')
        token=secrets.token_urlsafe(32)
        return token if consumer(code,owner,device_id,name,platform,public_key,token) else None
