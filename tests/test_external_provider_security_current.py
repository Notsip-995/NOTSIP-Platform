from pathlib import Path


def test_outbound_information_providers_require_permitted_endpoints():
    text=Path('src/notsip/information_services.py').read_text(encoding='utf-8')
    assert "def _public_provider_url" in text
    assert "httpx.AsyncClient(timeout=45,trust_env=False,follow_redirects=False)" in text
    assert "self.token and _public_provider_url(self.provider_url)" in text
    assert "navigation provider endpoint is not a permitted public HTTPS endpoint" in text
