import asyncio,json
import pytest
from notsip.business_admin import BusinessAdminAdapter,BusinessAdminUnavailable

class Response:
    def __init__(self,payload,status=200):self.payload=payload;self.status_code=status
    def raise_for_status(self):
        if self.status_code>=400:raise RuntimeError(f'HTTP {self.status_code}')
    def json(self):return self.payload

class Client:
    def __init__(self,*args,**kwargs):self.calls=[]
    async def __aenter__(self):return self
    async def __aexit__(self,*args):return False
    async def post(self,url,**kwargs):
        self.calls.append((url,kwargs))
        return Response({'success':True,'verified':True,'echo':kwargs.get('json') or {}})


def test_business_query_fails_closed_when_unconfigured():
    with pytest.raises(BusinessAdminUnavailable):asyncio.run(BusinessAdminAdapter().query('status'))


def test_business_requires_https_for_remote_provider(monkeypatch):
    adapter=BusinessAdminAdapter('http://203.0.113.10')
    with pytest.raises(ValueError,match='requires HTTPS'):
        asyncio.run(adapter.query('status'))


def test_business_query_posts_operation(monkeypatch):
    client=Client();monkeypatch.setattr('notsip.business_admin.httpx.AsyncClient',lambda *a,**k:client)
    result=asyncio.run(BusinessAdminAdapter('https://example.com','secret').query('inventory',{'site':'main'}))
    assert result['status']=='SUCCESS' and result['verified'] is True
    assert client.calls[0][1]['json']['operation']=='inventory'
    assert client.calls[0][1]['headers']['Authorization']=='Bearer secret'


def test_business_action_reports_provider_verification(monkeypatch):
    client=Client();monkeypatch.setattr('notsip.business_admin.httpx.AsyncClient',lambda *a,**k:client)
    result=asyncio.run(BusinessAdminAdapter('https://example.com','secret').action('provision',{'target':'user-1'}))
    assert result['status']=='SUCCESS' and result['verified'] is True
