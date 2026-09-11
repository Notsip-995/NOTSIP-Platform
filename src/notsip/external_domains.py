from __future__ import annotations
import ipaddress,socket
from urllib.parse import urlsplit
import httpx
from .policy import Risk
from .tools import Tool

MAX_RESPONSE_BYTES=5*1024*1024

def _public_https(url):
    p=urlsplit(str(url).strip())
    if p.scheme!='https' or not p.hostname:raise ValueError('external integration endpoint must use HTTPS')
    if p.username or p.password:raise ValueError('external integration endpoint must not contain credentials')
    host=p.hostname
    try:
        infos=socket.getaddrinfo(host,p.port or 443,type=socket.SOCK_STREAM)
        for info in infos:
            ip=ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:raise ValueError('external integration endpoint resolved to a non-public address')
    except socket.gaierror as exc:raise ValueError(f'external integration host resolution failed: {host}') from exc
    return p

class ExternalDomainAdapter:
    def __init__(self,settings):self.settings=settings
    async def _request(self,url,method='GET',token='',params=None,json_body=None):
        _public_https(url)
        headers={'Accept':'application/json'}
        if token:headers['Authorization']='Bearer '+token
        async with httpx.AsyncClient(timeout=30,follow_redirects=False) as client:
            r=await client.request(method,url,headers=headers,params=params,json=json_body)
            if r.status_code in {301,302,303,307,308}:raise RuntimeError('external integration redirect rejected')
            r.raise_for_status()
            if len(r.content)>MAX_RESPONSE_BYTES:raise RuntimeError('external integration response exceeded safety limit')
            if not r.content:return {'status':'SUCCESS','provider_status':r.status_code}
            try:data=r.json()
            except ValueError:return {'status':'SUCCESS','provider_status':r.status_code,'content_type':r.headers.get('content-type',''),'data':r.text[:MAX_RESPONSE_BYTES]}
            return {'status':'SUCCESS','provider_status':r.status_code,'data':data}
    async def flight_plan(self,origin,destination,departure_time='',constraints=None):
        url=str(getattr(self.settings,'flight_planning_url','')).strip()
        if not url:return {'status':'BLOCKED_BY_EXTERNAL_ENVIRONMENT','error':'flight planning endpoint is not configured'}
        payload={'origin':origin,'destination':destination,'departure_time':departure_time,'constraints':constraints or {}}
        return await self._request(url.rstrip('/')+'/plan','POST',getattr(self.settings,'flight_planning_token',''),json_body=payload)
    async def remote_sensing(self,query,location='',start='',end=''):
        url=str(getattr(self.settings,'remote_sensing_url','')).strip()
        if not url:return {'status':'BLOCKED_BY_EXTERNAL_ENVIRONMENT','error':'remote sensing endpoint is not configured'}
        return await self._request(url.rstrip('/')+'/query','GET',getattr(self.settings,'remote_sensing_token',''),params={'query':query,'location':location,'start':start,'end':end})
    async def remote_compute(self,code,inputs=None,language='python'):
        url=str(getattr(self.settings,'remote_compute_url','')).strip()
        if not url:return {'status':'BLOCKED_BY_EXTERNAL_ENVIRONMENT','error':'remote compute endpoint is not configured'}
        return await self._request(url.rstrip('/')+'/execute','POST',getattr(self.settings,'remote_compute_token',''),json_body={'code':code,'inputs':inputs or {},'language':language})

def attach(registry,settings):
    adapter=ExternalDomainAdapter(settings)
    if registry.get('flight_plan') is None:registry.add(Tool('flight_plan','Request a route/flight plan from the configured aviation planning provider.','FLIGHT_PLANNING',Risk.MEDIUM,{'type':'object','properties':{'origin':{'type':'string'},'destination':{'type':'string'},'departure_time':{'type':'string'},'constraints':{'type':'object'}},'required':['origin','destination']},adapter.flight_plan))
    if registry.get('remote_sensing_query') is None:registry.add(Tool('remote_sensing_query','Query the configured remote-sensing/satellite data provider.','INTERNET_SEARCH',Risk.MEDIUM,{'type':'object','properties':{'query':{'type':'string'},'location':{'type':'string'},'start':{'type':'string'},'end':{'type':'string'}},'required':['query']},adapter.remote_sensing))
    if registry.get('remote_compute_execute') is None:registry.add(Tool('remote_compute_execute','Execute approved computation through the configured remote compute provider.','CODE_EXECUTION',Risk.HIGH,{'type':'object','properties':{'code':{'type':'string'},'inputs':{'type':'object'},'language':{'type':'string'}},'required':['code']},adapter.remote_compute,True))
    return adapter
