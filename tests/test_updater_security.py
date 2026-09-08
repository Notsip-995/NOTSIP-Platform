from pathlib import Path
from types import SimpleNamespace
from notsip.updater import UpdateManager


def test_updater_trusts_only_configured_github_release_assets(tmp_path):
    settings=SimpleNamespace(github_repository='Notsip-995/NOTSIP-Platform',host='127.0.0.1',port=8765,windows_publisher_thumbprint='')
    updater=UpdateManager(tmp_path,settings)
    assert updater._trusted_asset('https://github.com/Notsip-995/NOTSIP-Platform/releases/download/v1.0/NOTSIP.exe')
    assert not updater._trusted_asset('https://example.com/NOTSIP.exe')
    assert not updater._trusted_asset('http://github.com/Notsip-995/NOTSIP-Platform/releases/download/v1.0/NOTSIP.exe')


def test_updater_requires_publisher_trust_on_windows(monkeypatch,tmp_path):
    settings=SimpleNamespace(github_repository='Notsip-995/NOTSIP-Platform',host='127.0.0.1',port=8765,windows_publisher_thumbprint='')
    updater=UpdateManager(tmp_path,settings)
    monkeypatch.setattr('notsip.updater.os.name','nt',raising=False)
    result=updater._verify_authenticode(Path(tmp_path/'NOTSIP.exe'))
    assert result['status']=='BLOCKED_BY_EXTERNAL_ENVIRONMENT'
