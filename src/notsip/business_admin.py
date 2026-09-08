from __future__ import annotations
import ipaddress, urllib.parse, socket
import httpx

class BusinessAdminUnavailable(RuntimeError):
    pass

def _public_host(host: str) -> bool:
    value=str(host or '').strip().lower()
    if value in {'localhost','localhost.localdomain'}:return False
    try:
        infos=socket.getaddrinfo(value,None,type=socket.SOCK_STREAM)
        return bool(infos) and all(not any(getattr(ipaddress.ip_address(a[4][0]),name) for name in ('is_private','is_loopback','is_link_local','is_multicast','is_reserved')) for a in infos)
    except Exception:return False

class BusinessAdminAdapter:
    """Provider-neutral adapter for authorized enterprise/business administration."""
    def __init__(self,base_url='',token=''):
        self.base_url=str(base_url or '').strip().rstrip('/')
        self.token=str(token or '').strip()
    @property
    def configured(self):return bool(self.base_url and self.token)
    def _url(self,path=''):
        if not self.configured:raise BusinessAdminUnavailable('business administration adapter is not configured')
        parsed=urllib.parse.urlparse(self.base_url)
        if parsed.scheme not in {'https','http'} or not parsed.hostname or parsed.username or parsed.password:raise ValueError('business administration requires a valid HTTP(S) base URL')
        if parsed.scheme!='https' and not (parsed.hostname in {'127.0.0.1','::1','localhost','localhost.localdomain'}):raise ValueError('business administration requires HTTPS for non-loopback providers')
        if parsed.scheme=='https' and not _public_host(parsed.hostname):raise ValueError('business administration HTTPS endpoint resolves to a private, loopback, link-local, multicast, or reserved address')
        clean='/' + str(path or '').lstrip('/')
        if '..' in urllib.parse.urlparse(clean).path.split('/'):raise ValueError('invalid business administration path')
        return self.base_url + clean
    def _headers(self):return {'Authorization':'Bearer '+self.token}
    async def query(self,operation='',params=None):
        url=self._url('query');payload={'operation':str(operation or 'status'),'params':params or {}}
        async with httpx.AsyncClient(timeout=20) as client:
            response=await client.post(url,json=payload,headers=self._headers());response.raise_for_status();data=response.json()
        return {'status':'SUCCESS','verified':False,'operation':payload['operation'],'data':data,'verification':{'transport':'HTTP 2xx','authoritative_state':bool(data.get('authoritative',False)),'independently_verified':bool(data.get('independently_verified',False))}}
    async def action(self,operation,payload=None):
        url=self._url('action');name=str(operation or '').strip()
        if not name:raise ValueError('operation is required')
        body={'operation':name,'payload':payload or {}}
        async with httpx.AsyncClient(timeout=30) as client:
            response=await client.post(url,json=body,headers=self._headers());response.raise_for_status();data=response.json()
        if 'success' not in data:return {'status':'UNKNOWN','verified':False,'operation':name,'data':data,'verification':{'transport':'HTTP 2xx','provider_success_field_present':False,'independently_verified':False}}
        succeeded=bool(data.get('success'));independently_verified=bool(data.get('independently_verified',False))
        return {'status':'SUCCESS' if succeeded else 'FAILURE','verified':independently_verified,'operation':name,'data':data,'verification':{'transport':'HTTP 2xx','provider_success_field_present':True,'independently_verified':independently_verified}}
