from pathlib import Path
from types import SimpleNamespace
from notsip.updater import UpdateManager


def test_update_health_probe_defaults_to_local_healthz(tmp_path):
    settings=SimpleNamespace(host='0.0.0.0',port=8765,github_repository='Notsip-995/NOTSIP-Platform',windows_publisher_thumbprint='')
    manager=UpdateManager(tmp_path,settings)
    assert manager.health_url=='http://127.0.0.1:8765/healthz'


def test_update_rejects_non_frozen_install(tmp_path):
    settings=SimpleNamespace(host='127.0.0.1',port=8765,github_repository='Notsip-995/NOTSIP-Platform',windows_publisher_thumbprint='')
    manager=UpdateManager(tmp_path,settings)
    try:manager.install_and_verify(Path(tmp_path/'new.exe'))
    except RuntimeError as exc:assert 'frozen installation' in str(exc)
    else:raise AssertionError('non-frozen updater unexpectedly attempted replacement')


def test_updater_source_contains_stop_before_copy(tmp_path):
    source=Path(__file__).parents[1]/'src'/'notsip'/'updater.py'
    text=source.read_text(encoding='utf-8')
    assert 'Stop-Process -Id' in text and 'Copy-Item -Force' in text and 'healthz' in text
