from __future__ import annotations
import httpx
class OpenAICompatible:
    def __init__(self,base_url,api_key,model): self.base_url=(base_url or '').rstrip('/'); self.api_key=api_key or ''; self.model=model or ''
    @property
    def enabled(self): return bool(self.base_url and self.model)
    async def chat(self,messages,tools):
        if not self.enabled: raise RuntimeError('LLM provider is not configured')
        headers={'Content-Type':'application/json'}
        if self.api_key: headers['Authorization']='Bearer '+self.api_key
        body={'model':self.model,'messages':messages,'temperature':0.2}
        if tools: body['tools']=tools
        async with httpx.AsyncClient(timeout=120) as c:
            r=await c.post(self.base_url+'/chat/completions',headers=headers,json=body); r.raise_for_status(); return r.json()
