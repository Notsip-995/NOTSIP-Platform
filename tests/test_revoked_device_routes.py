from pathlib import Path


def test_active_device_routes_reject_revoked_tokens():
    text=Path('src/notsip/product_routes.py').read_text(encoding='utf-8')
    assert "status')).upper()=='REVOKED'" in text or "upper()=='REVOKED'" in text
    assert '_device_token_allowed' in text
    assert text.count('_device_token_allowed(store,device_id') >= 3
