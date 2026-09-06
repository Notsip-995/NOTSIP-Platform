from __future__ import annotations
import base64, httpx
from .config import settings

class Provider:
    def __init__(self, base='', key='', model='', fallback_base='', fallback_key='', fallback_model=''):
        self.base=(base or '').rstrip('/')
        self.key=key or ''
        self.model=model or ''
        self.fallback_base=(fallback_base or '').rstrip('/')
        self.fallback_key=fallback_key or ''
        self.fallback_model=fallback_model or ''

    @property
    def enabled(self):
        base=(settings.llm_base_url or self.base).rstrip('/')
        model=settings.llm_model or self.model
        return bool(base and model)

    @property
    def fallback_enabled(self):
        base=(settings.fallback_llm_base_url or self.fallback_base).rstrip('/')
        model=settings.fallback_llm_model or self.fallback_model
        return bool(base and model)

    def _current_primary(self):
        return ((settings.llm_base_url or self.base).rstrip('/'), settings.llm_api_key or self.key, settings.llm_model or self.model)

    def _current_fallback(self):
        return ((settings.fallback_llm_base_url or self.fallback_base).rstrip('/'), settings.fallback_llm_api_key or self.fallback_key, settings.fallback_llm_model or self.fallback_model)

    async def _chat(self, base, key, model, messages, tools=None):
        if not base or not model: raise RuntimeError('provider endpoint/model not configured')
        h={'Content-Type':'application/json'}
        if key:h['Authorization']='Bearer '+key
        body={'model':model,'messages':messages,'temperature':0.2}
        if tools: body['tools']=tools
        async with httpx.AsyncClient(timeout=120) as c:
            r=await c.post(base.rstrip('/')+'/chat/completions',headers=h,json=body);r.raise_for_status();return r.json()

    async def chat(self,messages,tools=None):
        base,key,model=self._current_primary()
        if base and model:
            try:return await self._chat(base,key,model,messages,tools)
            except Exception:
                fbase,fkey,fmodel=self._current_fallback()
                if not fbase or not fmodel: raise
                return await self._chat(fbase,fkey,fmodel,messages,tools)
        fbase,fkey,fmodel=self._current_fallback()
        if fbase and fmodel:return await self._chat(fbase,fkey,fmodel,messages,tools)
        raise RuntimeError('no usable model provider configured')

    async def vision(self,prompt,image_bytes,mime='image/png'):
        data='data:'+mime+';base64,'+base64.b64encode(image_bytes).decode()
        return await self.chat([{'role':'user','content':[{'type':'text','text':prompt},{'type':'image_url','image_url':{'url':data}}]}])
