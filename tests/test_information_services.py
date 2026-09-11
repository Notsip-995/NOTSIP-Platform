import asyncio
import json
from notsip.information_services import NewsService,WeatherService,RoadNavigationService,FlightPlanningService,ExternalInformationUnavailable

class Response:
    def __init__(self,payload,status=200):self.payload=payload;self.status_code=status;self.content=json.dumps(payload).encode()
    def raise_for_status(self):
        if self.status_code>=400:raise RuntimeError(f'HTTP {self.status_code}')
    def json(self):return self.payload

class Client:
    def __init__(self,*args,**kwargs):self.calls=[]
    async def __aenter__(self):return self
    async def __aexit__(self,*args):return False
    async def get(self,url,**kwargs):
        self.calls.append(('GET',url,kwargs))
        if 'geocoding-api.open-meteo.com' in url:return Response({'results':[{'name':'Kigali','country':'Rwanda','latitude':-1.95,'longitude':30.06}]})
        if 'api.open-meteo.com' in url:return Response({'timezone':'Africa/Kigali','daily':{'time':['2026-09-09']}})
        if 'router.project-osrm.org' in url:return Response({'routes':[{'distance':1000,'duration':120,'legs':[]}]})
        return Response({'results':[]})
    async def post(self,url,**kwargs):return Response({'id':'job'})


def test_weather_uses_geocoding_then_forecast(monkeypatch):
    client=Client();monkeypatch.setattr('notsip.information_services.httpx.AsyncClient',lambda *a,**k:client)
    result=asyncio.run(WeatherService().forecast('Kigali',1))
    assert result['status']=='SUCCESS' and result['location']['name']=='Kigali'
    assert len(client.calls)==2


def test_news_fails_closed_without_key():
    try:asyncio.run(NewsService('').search('NOTSIP'))
    except ExternalInformationUnavailable as exc:assert 'news search is not configured' in str(exc)
    else:raise AssertionError('news must fail closed when no provider key exists')


def test_navigation_returns_route_without_vehicle_control(monkeypatch):
    client=Client();monkeypatch.setattr('notsip.information_services.httpx.AsyncClient',lambda *a,**k:client)
    result=asyncio.run(RoadNavigationService().route(-1.95,30.06,-1.97,30.08))
    assert result['status']=='SUCCESS' and result['distance_m']==1000


def test_flight_planning_fails_closed_without_provider():
    try:asyncio.run(FlightPlanningService().plan({'origin':'KGL','destination':'EBB'}))
    except ExternalInformationUnavailable as exc:assert 'aviation/flight planning provider is not configured' in str(exc)
    else:raise AssertionError('flight planning must fail closed without provider')
