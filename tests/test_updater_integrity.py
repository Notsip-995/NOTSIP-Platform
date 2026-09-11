from types import SimpleNamespace
from notsip.updater import UpdateManager


def test_updater_rejects_untrusted_redirect_hosts(tmp_path):
    settings=SimpleNamespace(github_repository='Notsip-995/NOTSIP-Platform',host='127.0.0.1',port=8765,windows_publisher_thumbprint='')
    updater=UpdateManager(tmp_path,settings)
    assert updater._trusted_asset('https://github.com/Notsip-995/NOTSIP-Platform/releases/download/v1.0.0/NOTSIP.exe') is True
    assert updater._trusted_redirect('https://release-assets.githubusercontent.com/example.exe') is True
    assert updater._trusted_redirect('https://evil.example/example.exe') is False
    assert updater._trusted_redirect('http://release-assets.githubusercontent.com/example.exe') is False
