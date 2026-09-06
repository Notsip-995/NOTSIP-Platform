from pathlib import Path


def test_launcher_source_has_frozen_resource_and_port_protection():
    text = Path("src/notsip/__main__.py").read_text(encoding="utf-8")
    assert "_MEIPASS" in text
    assert "_select_port" in text
    assert "already running" in text


def test_ui_is_packaged_by_build_script():
    text = Path("scripts/build_exe.ps1").read_text(encoding="utf-8")
    assert '--add-data "ui.html;."' in text
    assert "dist\\NOTSIP.exe" in text
