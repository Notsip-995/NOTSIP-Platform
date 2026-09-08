from __future__ import annotations
import ipaddress,socket,time
from urllib.parse import urlparse,quote
import httpx

class AdapterUnavailable(RuntimeError): pass

def _public_url(url:str)->bool:
    p=urlparse(str(url))
    if p.scheme!='https' or not p.hostname:return False
    try:
        ip=ipaddress.ip_address(socket.gethostbyname(p.hostname));return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved)
    except Exception:return False

class RemoteComputeAdapter:
    def __init__(self,endpoint='',token=''):self.endpoint=endpoint.rstrip('/');self.token=token
    @property
    def configured(self):return bool(self.endpoint and self.token and _public_url(self.endpoint))
    async def submit(self,job_type,payload):
        if not self.configured:raise AdapterUnavailable('remote compute adapter is not configured')
        async with httpx.AsyncClient(timeout=30) as c:r=await c.post(self.endpoint+'/jobs',json={'type':job_type,'payload':payload or {}},headers={'Authorization':'Bearer '+self.token});r.raise_for_status();return {'status':'QUEUED','job':r.json()}

class RemoteSensingAdapter:
    def __init__(self,endpoint='',token=''):self.endpoint=endpoint.rstrip('/');self.token=token
    @property
    def configured(self):return bool(self.endpoint and self.token and _public_url(self.endpoint))
    async def query(self,params):
        if not self.configured:raise AdapterUnavailable('remote sensing adapter is not configured')
        async with httpx.AsyncClient(timeout=45) as c:r=await c.get(self.endpoint+'/query',params=params or {},headers={'Authorization':'Bearer '+self.token});r.raise_for_status();return {'status':'SUCCESS','data':r.json(),'retrieved_at':time.time()}
    async def satellite_query(self,bbox,start,end,scene_id='',authorized=False):
        if not authorized:raise PermissionError('satellite/remote-sensing access requires explicit lawful authorization')
        if not self.configured:raise AdapterUnavailable('remote sensing adapter is not configured')
        params={'bbox':bbox,'start':start,'end':end}
        if scene_id:params['scene_id']=scene_id
        async with httpx.AsyncClient(timeout=60) as c:r=await c.get(self.endpoint+'/satellite/query',params=params,headers={'Authorization':'Bearer '+self.token});r.raise_for_status();d=r.json()
        return {'status':'SUCCESS','data':d,'provenance':{'provider':self.endpoint,'retrieved_at':time.time(),'authorized':True},'analysis':{'geolocation':True,'temporal_window':{'start':start,'end':end},'correlation_ready':True}}

class HomeAdapter:
    def __init__(self,endpoint='',token=''):self.endpoint=endpoint.rstrip('/');self.token=token
    @property
    def configured(self):return bool(self.endpoint and self.token and _public_url(self.endpoint))
    async def command(self,device_id,action,payload=None):
        if not self.configured:raise AdapterUnavailable('home/building adapter is not configured')
        path=quote(str(device_id),safe='')
        async with httpx.AsyncClient(timeout=20) as c:r=await c.post(self.endpoint+'/devices/'+path+'/commands',json={'action':action,'payload':payload or {}},headers={'Authorization':'Bearer '+self.token});r.raise_for_status();d=r.json()
        return {'status':'QUEUED' if d.get('status') in {'QUEUED','ACCEPTED'} else d.get('status','UNKNOWN'),'device_id':device_id,'action':action,'provider_result':d}

class BiometricTelemetryAdapter:
    def __init__(self,endpoint='',token=''):self.endpoint=endpoint.rstrip('/');self.token=token
    @property
    def configured(self):return bool(self.endpoint and self.token and _public_url(self.endpoint))
    async def latest(self):
        if not self.configured:raise AdapterUnavailable('biometric telemetry adapter is not configured')
        async with httpx.AsyncClient(timeout=20) as c:r=await c.get(self.endpoint+'/latest',headers={'Authorization':'Bearer '+self.token});r.raise_for_status();data=r.json()
        return {'status':'SUCCESS','measurement':data,'interpretation':None,'warning':None,'diagnosis':None,'is_diagnosis':False,'retrieved_at':time.time()}
