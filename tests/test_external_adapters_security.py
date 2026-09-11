from pathlib import Path


def test_external_adapters_reject_private_urls_and_redirects():
    text=Path('src/notsip/external_adapters.py').read_text(encoding='utf-8')
    assert "p.scheme!='https'" in text
    assert 'getaddrinfo' in text
    assert "response.is_redirect or response.is_permanent_redirect" in text
    assert 'follow_redirects=False' in text
    assert 'trust_env=False' in text
    assert 'external adapter response exceeded safety limit' in text
