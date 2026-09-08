from pathlib import Path


def test_satellite_tool_schema_does_not_expose_caller_authorization_flag():
    source=Path('src/notsip/satellite_tool_hardening.py').read_text(encoding='utf-8')
    assert "'authorized'" not in source
    assert "Risk.HIGH" in source
    assert 'adapter.satellite_query' in source


def test_canonical_runtime_installs_satellite_tool_hardening_after_advanced_intelligence():
    source=Path('src/notsip/core_runtime.py').read_text(encoding='utf-8')
    assert 'attach_advanced_intelligence' in source
    assert 'attach_satellite_tool_hardening' in source
