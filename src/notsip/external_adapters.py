import ipaddress,socket,time
from urllib.parse import urlparse,quote
import httpx
from .policy import Risk
from .tools import Tool
from .execution_gate import ToolExecutionGate
from .httpcheck import ensure_httpx_redirect_attributes

class AdapterUnavailable(RuntimeError): pass
MAX_ADAPTER_RESPONSE_BYTES=10*1024*1024

ensure_httpx_redirect_attributes()

def _public_url(url:str)->bool:
    p=urlparse(str(url))
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.query or p.fragment:return False
    try:
        infos=socket.getaddrinfo(p.hostname,p.port or 443,type=socket.SOCK_STREAM);ips={ipaddress.ip_address(info[4][0]) for info in infos}
        return bool(ips) and all(not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved) for ip in ips)
    except Exception:return False

def _json_response(response):
    if response.is_redirect or response.is_permanent_redirect:raise RuntimeError('external adapter redirect rejected')
    response.raise_for_status()
    if len(response.content)>MAX_ADAPTER_RESPONSE_BYTES:raise RuntimeError('external adapter response exceeded safety limit')
    return response.json()

class RemoteComputeAdapter:
    def __init__(self,endpoint='',token=''):self.endpoint=endpoint.rstrip('/');self.token=token
    @property
    def configured(self):return bool(self.endpoint and self.token and _public_url(self.endpoint))
    async def submit(self,job_type,payload):
        if not self.configured:raise AdapterUnavailable('remote compute adapter is not configured')
        async with httpx.AsyncClient(timeout=30,follow_redirects=False,trust_env=False) as c:r=await c.post(self.endpoint+'/jobs',json={'type':job_type,'payload':payload or {}},headers={'Authorization':'Bearer '+self.token});d=_json_response(r)
        return {'status':'QUEUED','job':d}

class RemoteSensingAdapter:
    def __init__(self,endpoint='',token=''):self.endpoint=endpoint.rstrip('/');self.token=token
    @property
    def configured(self):return bool(self.endpoint and self.token and _public_url(self.endpoint))
    async def query(self,params):
        if not self.configured:raise AdapterUnavailable('remote sensing adapter is not configured')
        async with httpx.AsyncClient(timeout=45,follow_redirects=False,trust_env=False) as c:r=await c.get(self.endpoint+'/query',params=params or {},headers={'Authorization':'Bearer '+self.token});d=_json_response(r)
        return {'status':'SUCCESS','data':d,'retrieved_at':time.time()}
    async def satellite_query(self,bbox,start,end,scene_id='',authorized=False):
        if not authorized:raise PermissionError('satellite/remote-sensing access requires explicit lawful authorization')
        if not self.configured:raise AdapterUnavailable('remote sensing adapter is not configured')
        params={'bbox':bbox,'start':start,'end':end}
        if scene_id:params['scene_id']=scene_id
        async with httpx.AsyncClient(timeout=60,follow_redirects=False,trust_env=False) as c:r=await c.get(self.endpoint+'/satellite/query',params=params,headers={'Authorization':'Bearer '+self.token});d=_json_response(r)
        return {'status':'SUCCESS','data':d,'provenance':{'provider':self.endpoint,'retrieved_at':time.time(),'authorized':True},'analysis':{'geolocation':True,'temporal_window':{'start':start,'end':end},'correlation_ready':True}}

class HomeAdapter:
    def __init__(self,endpoint='',token=''):self.endpoint=endpoint.rstrip('/');self.token=token
    @property
    def configured(self):return bool(self.endpoint and self.token and _public_url(self.endpoint))
    async def command(self,device_id,action,payload=None):
        if not self.configured:raise AdapterUnavailable('home/building adapter is not configured')
        path=quote(str(device_id),safe='')
        async with httpx.AsyncClient(timeout=20,follow_redirects=False,trust_env=False) as c:r=await c.post(self.endpoint+'/devices/'+path+'/commands',json={'action':action,'payload':payload or {}},headers={'Authorization':'Bearer '+self.token});d=_json_response(r)
        return {'status':'QUEUED' if d.get('status') in {'QUEUED','ACCEPTED'} else d.get('status','UNKNOWN'),'device_id':device_id,'action':action,'provider_result':d,'verified':False,'note':'provider accepted the command; physical device state was not independently verified'}

class BiometricTelemetryAdapter:
    def __init__(self,endpoint='',token=''):self.endpoint=endpoint.rstrip('/');self.token=token
    @property
    def configured(self):return bool(self.endpoint and self.token and _public_url(self.endpoint))
    async def latest(self):
        if not self.configured:raise AdapterUnavailable('biometric telemetry adapter is not configured')
        async with httpx.AsyncClient(timeout=20,follow_redirects=False,trust_env=False) as c:r=await c.get(self.endpoint+'/latest',headers={'Authorization':'Bearer '+self.token});data=_json_response(r)
        return {'status':'SUCCESS','measurement':data,'interpretation':None,'warning':None,'diagnosis':None,'is_diagnosis':False,'retrieved_at':time.time()}

def attach(registry,settings):
    home=HomeAdapter(getattr(settings,'home_adapter_url',''),getattr(settings,'home_adapter_token',''))
    biometric=BiometricTelemetryAdapter(getattr(settings,'biometric_adapter_url',''),getattr(settings,'biometric_adapter_token',''))
    if registry.get('home_command') is None:
        registry.add(Tool('home_command','Issue a command to an authorized home/building device through the configured adapter. Provider acceptance is not physical-state verification.','HOME_AUTOMATION',Risk.HIGH,{'type':'object','properties':{'device_id':{'type':'string'},'action':{'type':'string'},'payload':{'type':'object'}},'required':['device_id','action']},home.command,True))
    if registry.get('biometric_latest') is None:
        registry.add(Tool('biometric_latest','Read the latest authorized biometric telemetry; interpret it as telemetry, not diagnosis.','BIOMETRIC_READ',Risk.MEDIUM,{'type':'object','properties':{}},biometric.latest))
    ToolExecutionGate.wrap_registry(registry)
    return home,biometric