from __future__ import annotations
import secrets,hashlib
class Pairing:
    def __init__(self,store):self.store=store
    def create_code(self):return self.store.create_pair_code()
    def consume(self,code,device_id,name,platform,public_key=''):
        if not self.store.consume_pair_code(code):return None
        token=secrets.token_urlsafe(32);self.store.pair_device(device_id,name,platform,public_key,token);return token
