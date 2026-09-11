import asyncio
import json
import pytest
from notsip.voice_identity import SpeakerIdentityAdapter,SpeakerIdentityUnavailable

class Response:
    def __init__(self,payload,status=200):self.payload=payload;self.status_code=status
    def raise_for_status(self):
        if self.status_code>=400:raise RuntimeError(f'HTTP {self.status_code}')
    def json(self):return self.payload

class Client:
    def __init__(self,*args,**kwargs):pass
    async def __aenter__(self):return self
    async def __aexit__(self,*args):return False
    async def post(self,url,**kwargs):return Response({'verified':True,'speaker_id':'issuer:user-a','confidence':0.94})


def test_unconfigured_speaker_verification_fails_closed():
    with pytest.raises(SpeakerIdentityUnavailable):asyncio.run(SpeakerIdentityAdapter().verify(b'audio'))


def test_speaker_verification_requires_https():
    with pytest.raises(ValueError,match='HTTPS'):
        asyncio.run(SpeakerIdentityAdapter('http://identity.example').verify(b'audio'))


def test_speaker_verification_returns_verified_identity(monkeypatch):
    monkeypatch.setattr('notsip.voice_identity.httpx.AsyncClient',lambda *a,**k:Client())
    result=asyncio.run(SpeakerIdentityAdapter('https://identity.example','tok').verify(b'audio'))
    assert result['status']=='SUCCESS' and result['verified'] is True
    assert result['speaker_id']=='issuer:user-a' and result['confidence']==0.94
