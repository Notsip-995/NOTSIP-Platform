from pathlib import Path


def test_config_fails_closed_on_persisted_configuration_error():
    text=Path('src/notsip/config.py').read_text(encoding='utf-8')
    assert "failed to load persisted NOTSIP configuration" in text
    assert "failed to initialize NOTSIP configuration/security state" in text
    assert "except Exception:pass" not in text


def test_satellite_route_does_not_accept_caller_authorized_flag():
    text=Path('src/notsip/status_scope_hardening.py').read_text(encoding='utf-8')
    assert "'/api/remote/satellite'" in text
    assert "primary administrative actor required for satellite access" in text
    assert "authorized:bool=False" not in text
    assert "agent.run_tool('satellite_query'" in text
