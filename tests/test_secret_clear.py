from notsip.security import SecretStore
from notsip.config import settings
from notsip.provider import Provider


def test_secret_store_delete(tmp_path):
    store = SecretStore(tmp_path)
    store.set('NOTSIP_LLM_API_KEY', 'old-secret')
    assert store.get('NOTSIP_LLM_API_KEY') == 'old-secret'
    store.delete('NOTSIP_LLM_API_KEY')
    assert store.get('NOTSIP_LLM_API_KEY') is None


def test_provider_does_not_resurrect_cleared_secret(monkeypatch):
    monkeypatch.setattr(settings, 'llm_base_url', '')
    monkeypatch.setattr(settings, 'llm_model', '')
    monkeypatch.setattr(settings, 'llm_api_key', '')
    p = Provider('https://stale.example/v1', 'stale-secret', 'stale-model')
    assert p.enabled is False
    assert p._current_primary() == ('', '', '')
