import asyncio
from types import SimpleNamespace
from notsip.updater import UpdateManager


class Response:
    def __init__(self,text,status_code=200,headers=None):self.text=text;self.status_code=status_code;self.headers=headers or {};self.content=text.encode()
    @property
    def is_redirect(self):return 300 <= self.status_code < 400
    def raise_for_status(self):
        if self.status_code >= 400:raise RuntimeError(self.status_code)


class Client:
    def __init__(self,responses):self.responses=list(responses);self.calls=[]
    async def __aenter__(self):return self
    async def __aexit__(self,*args):return False
    async def get(self,url,headers=None):self.calls.append((url,dict(headers or {})));return self.responses.pop(0)


def test_manifest_must_match_artifact_name(monkeypatch,tmp_path):
    settings=SimpleNamespace(github_repository='Notsip-995/NOTSIP-Platform',port=8765)
    manager=UpdateManager(tmp_path,settings)
    import notsip.updater as module
    client=Client([Response('a'*64+'  OTHER.exe\n')])
    monkeypatch.setattr(module.httpx,'AsyncClient',lambda **kwargs:client)
    with __import__('pytest').raises(ValueError,match='different artifact'):
        asyncio.run(manager._fetch_manifest_sha('https://github.com/Notsip-995/NOTSIP-Platform/releases/download/v1.0.0/NOTSIP.exe.sha256','NOTSIP.exe'))


def test_manifest_redirect_does_not_forward_github_token(monkeypatch,tmp_path):
    settings=SimpleNamespace(github_repository='Notsip-995/NOTSIP-Platform',port=8765)
    manager=UpdateManager(tmp_path,settings)
    import notsip.updater as module
    client=Client([Response('',302,{'location':'https://release-assets.githubusercontent.com/manifest'}),Response('a'*64+'  NOTSIP.exe\n')])
    monkeypatch.setattr(module.httpx,'AsyncClient',lambda **kwargs:client)
    monkeypatch.setenv('NOTSIP_GITHUB_TOKEN','token')
    result=asyncio.run(manager._fetch_manifest_sha('https://github.com/Notsip-995/NOTSIP-Platform/releases/download/v1.0.0/NOTSIP.exe.sha256','NOTSIP.exe'))
    assert result=='a'*64
    assert client.calls[0][1]['Authorization']=='Bearer token'
    assert 'Authorization' not in client.calls[1][1]
