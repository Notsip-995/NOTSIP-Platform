from __future__ import annotations
import base64,httpx
class Provider:
    def __init__(self,base='',key='',model=''):self.base=(base or '').rstrip('/');self.key=key or '';self.model=model or ''
    @property
    def enabled(self):return bool(self.base and self.model)
    async def chat(self,messages,tools=None):
        if not self.enabled:raise RuntimeError('provider not configured')
        h={'Content-Type':'application/json'}
        if self.key:h['Authorization']='Bearer '+self.key
        b={'model':self.model,'messages':messages,'temperature':0.2}
        if tools:b['tools']=tools
        async with httpx.AsyncClient(timeout=120) as c:r=await c.post(self.base+'/chat/completions',headers=h,json=b);r.raise_for_status();return r.json()
    async def vision(self,prompt,image_bytes,mime='image/png'):
        if not self.enabled:raise RuntimeError('vision provider not configured')
        data='data:'+mime+';base64,'+base64.b64encode(image_bytes).decode();return await self.chat([{'role':'user','content':[{'type':'text','text':prompt},{'type':'image_url','image_url':{'url':data}}]}])
