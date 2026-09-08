from pathlib import Path

import pytest


def test_launcher_source_has_frozen_resource_and_port_protection():
    text = Path("src/notsip/__main__.py").read_text(encoding="utf-8")
    assert "_MEIPASS" in text
    assert "_select_port" in text
    assert "already running" in text


def test_ui_is_packaged_by_build_script():
    text = Path("scripts/build_exe.ps1").read_text(encoding="utf-8")
    assert '--add-data "ui.html;."' in text
    assert "dist\\NOTSIP.exe" in text


def test_remote_bind_requires_auth(monkeypatch):
    import notsip.__main__ as launcher

    monkeypatch.setattr(launcher.settings, "api_key", "")
    monkeypatch.setattr(launcher.settings, "auth_mode", "api_key")
    with pytest.raises(RuntimeError, match="unauthenticated non-loopback bind"):
        launcher._validate_bind_security("0.0.0.0")


def test_loopback_bind_allows_local_setup_without_auth(monkeypatch):
    import notsip.__main__ as launcher

    monkeypatch.setattr(launcher.settings, "api_key", "")
    monkeypatch.setattr(launcher.settings, "auth_mode", "api_key")
    for host in ("127.0.0.1", "localhost", "::1"):
        launcher._validate_bind_security(host)


def test_launcher_process_guard_refuses_corrupt_existing_lock(tmp_path):
    from notsip.launcher_guard import LauncherProcessGuard

    path=Path(tmp_path)/'runtime'/'instance.lock'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('{corrupt',encoding='utf-8')
    guard=LauncherProcessGuard(root=tmp_path)
    with pytest.raises(RuntimeError,match='instance lock is corrupt'):
        guard.acquire()
    assert path.exists()
