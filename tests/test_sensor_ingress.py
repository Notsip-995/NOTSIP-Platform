import asyncio,time
import pytest
from notsip.sensor_ingress import attach

class Store:
    def __init__(self):self.readings=[]
    def device_token_valid(self,device_id,token):return device_id=='phone-1' and token=='token-1'
    def row(self,sql,args):
        if 'FROM devices' in sql:return {'id':args[0],'name':'Phone','platform':'android','status':'ONLINE'}
        return None
    def fact(self,*args):self.readings.append(args)

class World:
    def __init__(self):self.items={}
    def upsert(self,eid,kind,name,data):self.items[eid]=(kind,name,data)

class Events:
    def __init__(self):self.events=[]
    async def publish(self,event):self.events.append(event);return []

class App:
    def post(self,path):
        def deco(fn):self.fn=fn;return fn
        return deco

class Request:pass


def test_sensor_report_updates_world_and_publishes():
    app=App();store=Store();world=World();events=Events();attach(app,store,world,events)
    r=Request()
    result=asyncio.run(app.fn({'sensor_type':'temperature','value':23.5,'unit':'C'},r,'phone-1','token-1'))
    assert result['status']=='SUCCESS' and result['verified'] is True
    assert 'device:phone-1:sensor:temperature' in world.items
    assert [e.type for e in events.events]==['sensor.temperature','sensor.reading']


def test_sensor_report_rejects_unknown_sensor_type():
    app=App();attach(app,Store(),World(),Events());r=Request()
    with pytest.raises(Exception,match='unsupported sensor_type'):
        asyncio.run(app.fn({'sensor_type':'unknown','value':1},r,'phone-1','token-1'))


def test_sensor_report_rejects_future_timestamp():
    app=App();attach(app,Store(),World(),Events());r=Request()
    with pytest.raises(Exception,match='implausibly future'):
        asyncio.run(app.fn({'sensor_type':'temperature','value':1,'observed_at':time.time()+1000},r,'phone-1','token-1'))


def test_sensor_report_requires_device_authentication():
    app=App();attach(app,Store(),World(),Events());r=Request()
    with pytest.raises(Exception,match='device authentication required'):
        asyncio.run(app.fn({'sensor_type':'temperature','value':1},r,'phone-1','bad-token'))
