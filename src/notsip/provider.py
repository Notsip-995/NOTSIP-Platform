from __future__ import annotations
import base64,httpx,ipaddress,socket
from urllib.parse import urlsplit
from .config import settings

MAX_MODEL_RESPONSE_BYTES=10*1024*1024


def _validate_endpoint(url):
    parsed=urlsplit(str(url).strip())
    if not parsed.hostname:raise ValueError('model provider endpoint must include a hostname')
    if parsed.username or parsed.password:raise ValueError('model provider endpoint must not contain credentials')
    if parsed.query or parsed.fragment:raise ValueError('model provider endpoint must not contain query or fragment')
    if parsed.scheme not in {'https','http'}:raise ValueError('model provider endpoint must use HTTP or HTTPS')
    infos=socket.getaddrinfo(parsed.hostname,parsed.port or (443 if parsed.scheme=='https' else 80),type=socket.SOCK_STREAM)
    ips={ipaddress.ip_address(info[4][0]) for info in infos}
    if parsed.scheme=='http' and not all(ip.is_loopback for ip in ips):raise ValueError('HTTP model provider endpoints are restricted to loopback addresses')
    if parsed.scheme=='https' and any(ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved for ip in ips):raise ValueError('model provider endpoint resolved to a non-public address')
    return parsed

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
        return bool((settings.llm_base_url or '').rstrip('/') and settings.llm_model)

    @property
    def fallback_enabled(self):
        return bool((settings.fallback_llm_base_url or '').rstrip('/') and settings.fallback_llm_model)

    def _current_primary(self):
        return ((settings.llm_base_url or '').rstrip('/'),settings.llm_api_key or '',settings.llm_model or '')

    def _current_fallback(self):
        return ((settings.fallback_llm_base_url or '').rstrip('/'),settings.fallback_llm_api_key or '',settings.fallback_llm_model or '')

    async def _chat(self,base,key,model,messages,tools=None):
        if not base or not model:raise RuntimeError('provider endpoint/model not configured')
        _validate_endpoint(base)
        h={'Content-Type':'application/json'}
        if key:h['Authorization']='Bearer '+key
        body={'model':model,'messages':messages,'temperature':0.2}
        if tools:body['tools']=tools
        async with httpx.AsyncClient(timeout=120,follow_redirects=False,trust_env=False) as c:
            r=await c.post(base.rstrip('/')+'/chat/completions',headers=h,json=body)
            if r.is_redirect or r.is_permanent_redirect:raise RuntimeError('model provider redirect rejected')
            r.raise_for_status()
            if len(r.content)>MAX_MODEL_RESPONSE_BYTES:raise RuntimeError('model provider response exceeded safety limit')
            return r.json()

    async def chat(self,messages,tools=None):
        base,key,model=self._current_primary()
        if base and model:
            try:return await self._chat(base,key,model,messages,tools)
            except Exception:
                fbase,fkey,fmodel=self._current_fallback()
                if not fbase or not fmodel:raise
                return await self._chat(fbase,fkey,fmodel,messages,tools)
        fbase,fkey,fmodel=self._current_fallback()
        if fbase and fmodel:return await self._chat(fbase,fkey,fmodel,messages,tools)
        raise RuntimeError('no usable model provider configured')

    async def vision(self,prompt,image_bytes,mime='image/png'):
        data='data:'+mime+';base64,'+base64.b64encode(image_bytes).decode()
        return await self.chat([{'role':'user','content':[{'type':'text','text':prompt},{'type':'image_url','image_url':{'url':data}}]}])
