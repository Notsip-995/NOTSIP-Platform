from __future__ import annotations
import base64, httpx

class Provider:
    def __init__(self, base='', key='', model='', fallback_base='', fallback_key='', fallback_model=''):
        self.base=(base or '').rstrip('/')
        self.key=key or ''
        self.model=model or ''
        self.fallback_base=(fallback_base or '').rstrip('/')
        self.fallback_key=fallback_key or ''
        self.fallback_model=fallback_model or ''

    @property
    def enabled(self): return bool(self.base and self.model)
    @property
    def fallback_enabled(self): return bool(self.fallback_base and self.fallback_model)

    async def _chat(self, base, key, model, messages, tools=None):
        if not base or not model: raise RuntimeError('provider endpoint/model not configured')
        h={'Content-Type':'application/json'}
        if key:h['Authorization']='Bearer '+key
        body={'model':model,'messages':messages,'temperature':0.2}
        if tools: body['tools']=tools
        async with httpx.AsyncClient(timeout=120) as c:
            r=await c.post(base+'/chat/completions',headers=h,json=body);r.raise_for_status();return r.json()

    async def chat(self,messages,tools=None):
        if self.enabled:
            try:return await self._chat(self.base,self.key,self.model,messages,tools)
            except Exception:
                if not self.fallback_enabled: raise
        if self.fallback_enabled:return await self._chat(self.fallback_base,self.fallback_key,self.fallback_model,messages,tools)
        raise RuntimeError('no usable model provider configured')

    async def vision(self,prompt,image_bytes,mime='image/png'):
        data='data:'+mime+';base64,'+base64.b64encode(image_bytes).decode()
        return await self.chat([{'role':'user','content':[{'type':'text','text':prompt},{'type':'image_url','image_url':{'url':data}}]}])
