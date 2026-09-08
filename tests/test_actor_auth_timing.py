from pathlib import Path


def test_actor_auth_uses_constant_time_api_key_comparison():
    text=Path('src/notsip/actor_context.py').read_text(encoding='utf-8')
    assert 'secrets.compare_digest(bearer,configured)' in text
    assert 'bearer==auth.settings.api_key' not in text
