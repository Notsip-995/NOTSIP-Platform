from __future__ import annotations
import hashlib,hmac,httpx
class Brave:
    def __init__(self,key): self.key=key or ''
    @property
    def enabled(self): return bool(self.key)
    async def search(self,q,count=5):
        if not self.enabled: raise RuntimeError('Brave Search is not configured')
        async with httpx.AsyncClient(timeout=20) as c:
            r=await c.get('https://api.search.brave.com/res/v1/web/search',params={'q':q,'count':count},headers={'Accept':'application/json','X-Subscription-Token':self.key}); r.raise_for_status(); data=r.json()
        return [{'title':x.get('title'),'url':x.get('url'),'description':x.get('description')} for x in data.get('web',{}).get('results',[])]
class Webhook:
    def __init__(self,secret): self.secret=(secret or '').encode()
    def verify(self,body,sig):
        if not self.secret: return True
        if not sig: return False
        return hmac.compare_digest(hmac.new(self.secret,body,hashlib.sha256).hexdigest(),sig)
