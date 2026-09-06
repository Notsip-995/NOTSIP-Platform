from __future__ import annotations
import hashlib,secrets,time
class Pairing:
    def __init__(self,store): self.store=store; self.pending={}
    def create_code(self,expires=600):
        code=f"{secrets.randbelow(10**6):06d}"; self.pending[code]=time.time()+expires; return code
    def consume(self,code,device_id,name,platform,public_key):
        exp=self.pending.get(code)
        if not exp or exp<time.time(): return None
        del self.pending[code]; token=secrets.token_urlsafe(32); self.store.pair_device(device_id,name,platform,public_key,hashlib.sha256(token.encode()).hexdigest()); return token
