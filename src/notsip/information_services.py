from __future__ import annotations
import ipaddress,math,socket,time
from urllib.parse import quote,urlparse
import httpx

class ExternalInformationUnavailable(RuntimeError):
    pass


def _public_provider_url(url):
    p=urlparse(str(url or '').strip())
    if p.scheme not in {'http','https'} or not p.hostname or p.username or p.password:return False
    if p.scheme=='http' and p.hostname not in {'127.0.0.1','::1','localhost','localhost.localdomain'}:return False
    if p.scheme=='https':
        try:
            infos=socket.getaddrinfo(p.hostname,None,type=socket.SOCK_STREAM)
            return bool(infos) and all(not any(getattr(ipaddress.ip_address(x[4][0]),name) for name in ('is_private','is_loopback','is_link_local','is_multicast','is_reserved')) for x in infos)
        except Exception:return False
    return True

class WeatherService:
    GEOCODE='https://geocoding-api.open-meteo.com/v1/search'
    FORECAST='https://api.open-meteo.com/v1/forecast'
    async def forecast(self,location,days=2,timezone='auto'):
        place=str(location or '').strip()
        if not place:raise ValueError('location is required')
        async with httpx.AsyncClient(timeout=20,follow_redirects=False,trust_env=False) as c:
            geo=await c.get(self.GEOCODE,params={'name':place,'count':1,'language':'en','format':'json'});geo.raise_for_status();results=(geo.json().get('results') or [])
            if not results:raise ExternalInformationUnavailable(f'location not found: {place}')
            g=results[0];forecast=await c.get(self.FORECAST,params={'latitude':g['latitude'],'longitude':g['longitude'],'daily':'weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max','forecast_days':max(1,min(int(days),16)),'timezone':timezone});forecast.raise_for_status();data=forecast.json()
        return {'status':'SUCCESS','location':{'name':g.get('name'),'country':g.get('country'),'latitude':g['latitude'],'longitude':g['longitude']},'retrieved_at':time.time(),'timezone':data.get('timezone'),'daily':data.get('daily',{})}

class NewsService:
    def __init__(self,api_key='',base_url='https://api.search.brave.com/res/v1/news/search'):self.api_key=api_key;self.base_url=base_url
    @property
    def configured(self):return bool(self.api_key and self.base_url and _public_provider_url(self.base_url))
    async def search(self,query,count=10):
        if not self.configured:raise ExternalInformationUnavailable('news search is not configured')
        async with httpx.AsyncClient(timeout=20,trust_env=False) as c:
            r=await c.get(self.base_url,params={'q':str(query).strip(),'count':max(1,min(int(count),20))},headers={'Accept':'application/json','X-Subscription-Token':self.api_key});r.raise_for_status();data=r.json()
        rows=[]
        for item in data.get('results',[]):rows.append({'title':item.get('title'),'url':item.get('url'),'description':item.get('description'),'age':item.get('age'),'source':(item.get('meta_url') or {}).get('hostname'),'published':item.get('age')})
        return {'status':'SUCCESS','query':query,'retrieved_at':time.time(),'results':rows}

class RoadNavigationService:
    def __init__(self,base_url='https://router.project-osrm.org'):self.base_url=str(base_url).rstrip('/')
    async def route(self,origin_lat,origin_lon,dest_lat,dest_lon,profile='driving'):
        for value in (origin_lat,origin_lon,dest_lat,dest_lon):
            if not isinstance(value,(int,float)) or not math.isfinite(float(value)):raise ValueError('coordinates must be finite numbers')
        profile=str(profile or 'driving').lower()
        if profile not in {'driving','walking','cycling'}:raise ValueError('unsupported route profile')
        if not _public_provider_url(self.base_url):raise ExternalInformationUnavailable('navigation provider endpoint is not a permitted public HTTPS endpoint')
        path=f"{self.base_url}/route/v1/{quote(profile,safe='')}/{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
        async with httpx.AsyncClient(timeout=30,trust_env=False,follow_redirects=False) as c:r=await c.get(path,params={'overview':'false','steps':'true'});r.raise_for_status();data=r.json()
        route=(data.get('routes') or [None])[0]
        if not route:return {'status':'FAILURE','error':'no route returned'}
        return {'status':'SUCCESS','provider':self.base_url,'distance_m':route.get('distance'),'duration_s':route.get('duration'),'legs':route.get('legs',[]),'retrieved_at':time.time()}

class FlightPlanningService:
    def __init__(self,provider_url='',token=''):self.provider_url=str(provider_url or '').rstrip('/');self.token=token
    @property
    def configured(self):return bool(self.provider_url and self.token and _public_provider_url(self.provider_url))
    async def plan(self,payload):
        if not self.configured:raise ExternalInformationUnavailable('aviation/flight planning provider is not configured')
        async with httpx.AsyncClient(timeout=45,trust_env=False,follow_redirects=False) as c:
            r=await c.post(self.provider_url+'/flight-plan',json=payload or {},headers={'Authorization':'Bearer '+self.token});r.raise_for_status();data=r.json()
        return {'status':'SUCCESS','provider_result':data,'retrieved_at':time.time(),'executed':False,'note':'Flight plan generated as data only; no aircraft control was requested.'}
