import asyncio
import json
from notsip.account_store import AccountStore
from notsip.oauth_services import OAuthService
from notsip.security import SecretStore


class FakeResponse:
    def __init__(self,status=200,payload=None):
        self.status_code=status;self._payload=payload or {};self.content=json.dumps(self._payload).encode()
    def raise_for_status(self):
        if self.status_code>=400:raise RuntimeError(f'HTTP {self.status_code}')
    def json(self):return self._payload


class FakeClient:
    calls=[]
    async def __aenter__(self):return self
    async def __aexit__(self,*args):return False
    async def request(self,method,url,headers=None,**kwargs):
        self.calls.append((method,url,headers or {},kwargs));return FakeResponse(201,{'id':'provider-event'})


def test_google_calendar_write_requires_write_scope(tmp_path):
    secrets=SecretStore(tmp_path);accounts=AccountStore(secrets);a=accounts.upsert('google','subject','user@example.com',scopes='openid profile email https://www.googleapis.com/auth/calendar')
    accounts.save_tokens(a['id'],{'access_token':'token'})
    svc=OAuthService(secrets,accounts)
    try:asyncio.run(svc.send_mail('google','to@example.com','s','body',a['id']))
    except PermissionError as exc:assert 'gmail.send' in str(exc)
    else:raise AssertionError('mail send must require gmail.send scope')


def test_microsoft_calendar_mutation_is_account_scoped_and_uses_patch(tmp_path,monkeypatch):
    secrets=SecretStore(tmp_path);accounts=AccountStore(secrets)
    a=accounts.upsert('microsoft','a','a@example.com',scopes='openid profile Calendars.ReadWrite Mail.Send')
    b=accounts.upsert('microsoft','b','b@example.com',scopes='openid profile Calendars.ReadWrite Mail.Send')
    accounts.save_tokens(a['id'],{'access_token':'token-a'})
    accounts.save_tokens(b['id'],{'access_token':'token-b'})
    fake=FakeClient();monkeypatch.setattr('notsip.oauth_services.httpx.AsyncClient',lambda *args,**kwargs:fake)
    result=asyncio.run(OAuthService(secrets,accounts).calendar_update('microsoft','event-1',{'title':'Updated'},a['id']))
    assert result['status']=='SUCCESS'
    assert fake.calls[0][0]=='PATCH'
    assert fake.calls[0][1].endswith('/me/calendar/events/event-1')
    assert fake.calls[0][2]['Authorization']=='Bearer token-a'
    assert 'subject' not in fake.calls[0][3]['json'] or fake.calls[0][3]['json']['subject']=='Updated'
    assert accounts.tokens(b['id'])['access_token']=='token-b'


def test_google_mail_send_does_not_require_delivery_claim(tmp_path,monkeypatch):
    secrets=SecretStore(tmp_path);accounts=AccountStore(secrets);a=accounts.upsert('google','subject','user@example.com',scopes='openid profile email https://www.googleapis.com/auth/gmail.send')
    accounts.save_tokens(a['id'],{'access_token':'token'})
    fake=FakeClient();monkeypatch.setattr('notsip.oauth_services.httpx.AsyncClient',lambda *args,**kwargs:fake)
    result=asyncio.run(OAuthService(secrets,accounts).send_mail('google','to@example.com','s','body',a['id']))
    assert result['provider_status']==201
    assert result['status']=='SUCCESS'
    assert 'delivered' not in result
