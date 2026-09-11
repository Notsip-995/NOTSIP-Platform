import pytest
from notsip.connectors import _public_host


def test_browser_network_policy_rejects_private_targets():
    assert _public_host('127.0.0.1') is False
    assert _public_host('localhost') is False


def test_browser_interaction_requires_playwright_and_public_url(monkeypatch):
    from notsip.connectors import Browser
    import asyncio
    from notsip.config import settings
    monkeypatch.setattr(settings,'browser_enabled',True)
    with pytest.raises(ValueError):
        asyncio.run(Browser().interact('http://127.0.0.1:8765',[]))
