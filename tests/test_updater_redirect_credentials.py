import hashlib
from types import SimpleNamespace
from notsip.updater import UpdateManager


class _Response:
    def __init__(self,status_code=200,headers=None,content=b'payload',url='https://release-assets.githubusercontent.com/a.exe'):
        self.status_code=status_code;self.headers=headers or {};self.content=content;self.url=url
    @property
    def is_redirect(self):return 300 <= self.status_code < 400
    def raise_for_status(self):
        if self.status_code >= 400:raise RuntimeError(f'HTTP {self.status_code}')


class _Client:
    def __init__(self,calls):self.calls=calls
    async def __aenter__(self):return self
    async def __aexit__(self,*args):return False
    async def get(self,url,headers=None):
        self.calls.append((url,dict(headers or {})))
        if len(self.calls)==1:return _Response(302,{'location':'https://release-assets.githubusercontent.com/a.exe'},url=url)
        return _Response(200,content=b'payload',url=url)


def test_updater_does_not_send_bearer_to_release_asset_redirect(monkeypatch,tmp_path):
    settings=SimpleNamespace(github_repository='Notsip-995/NOTSIP-Platform',host='127.0.0.1',port=8765,windows_publisher_thumbprint='')
    updater=UpdateManager(tmp_path,settings)
    calls=[]
    import notsip.updater as module
    monkeypatch.setattr(module.httpx,'AsyncClient',lambda **kwargs:_Client(calls))
    monkeypatch.setenv('NOTSIP_GITHUB_TOKEN','secret-token')
    digest=hashlib.sha256(b'payload').hexdigest()

    import asyncio
    result=asyncio.run(updater.download('https://github.com/Notsip-995/NOTSIP-Platform/releases/download/v1.0.0/NOTSIP.exe',digest))
    assert result['status']=='DOWNLOADED'
    assert calls[0][1].get('Authorization')=='Bearer secret-token'
    assert 'Authorization' not in calls[1][1]


def test_updater_restricts_self_install_to_managed_update_directory(tmp_path):
    settings=SimpleNamespace(github_repository='Notsip-995/NOTSIP-Platform',host='127.0.0.1',port=8765,windows_publisher_thumbprint='')
    updater=UpdateManager(tmp_path,settings)
    outside=tmp_path/'outside.exe';outside.write_bytes(b'x')
    try:
        updater._managed_update_path(outside)
    except ValueError as exc:
        assert 'managed updates directory' in str(exc)
    else:
        raise AssertionError('outside update path was accepted')
