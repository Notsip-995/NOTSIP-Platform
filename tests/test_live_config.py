from notsip.config import settings
from notsip.provider import Provider
from notsip.connectors import Web, Email, Browser
from notsip.policy import Policy, Risk
from notsip.security import SecretStore, AuthManager
import asyncio
import pytest

def test_provider_uses_saved_settings_live(monkeypatch):
    monkeypatch.setattr(settings, 'llm_base_url', 'https://primary.example/v1')
    monkeypatch.setattr(settings, 'llm_model', 'primary-model')
    monkeypatch.setattr(settings, 'llm_api_key', 'primary-key')
    monkeypatch.setattr(settings, 'fallback_llm_base_url', 'https://fallback.example/v1')
    monkeypatch.setattr(settings, 'fallback_llm_model', 'fallback-model')
    monkeypatch.setattr(settings, 'fallback_llm_api_key', 'fallback-key')
    p=Provider('', '', '', '', '', '')
    assert p.enabled
    assert p.fallback_enabled
    assert p._current_primary()==('https://primary.example/v1','primary-key','primary-model')
    assert p._current_fallback()==('https://fallback.example/v1','fallback-key','fallback-model')

def test_web_email_and_policy_follow_saved_settings(monkeypatch):
    monkeypatch.setattr(settings, 'brave_api_key', 'brave-key')
    web=Web('')
    assert web.enabled
    monkeypatch.setattr(settings, 'email_username', 'user@example.com')
    monkeypatch.setattr(settings, 'email_password', 'app-password')
    monkeypatch.setattr(settings, 'smtp_host', 'smtp.example.com')
    monkeypatch.setattr(settings, 'imap_host', 'imap.example.com')
    mail=Email('',587,'','','')
    assert mail.enabled
    assert mail._smtp_host=='smtp.example.com'
    assert mail._imap_host=='imap.example.com'
    monkeypatch.setattr(settings, 'autonomy_level', 4)
    policy=Policy(0)
    assert policy.decide(Risk.HIGH, destructive=True).allowed

def test_public_setup_state_contains_presence_without_secret_values(tmp_path, monkeypatch):
    from notsip.setup_hardening import _public_state
    class Mod:
        config_store=type('C',(),{'load':lambda self:{'version':2,'settings':{'llm_model':'model-name'}}})()
        settings=settings
        auth=type('A',(),{'secrets':SecretStore(tmp_path/'secrets')})()
    monkeypatch.setattr(settings, 'api_key', 'super-secret')
    state=_public_state(Mod)
    assert state['settings']['llm_model']=='model-name'
    assert 'api_key' not in state['settings']
    assert state['secret_configured']['api_key'] is True

def test_secret_store_empty_value_clears_secret(tmp_path):
    store=SecretStore(tmp_path)
    store.set('NOTSIP_TEST_SECRET','value')
    assert store.get('NOTSIP_TEST_SECRET')=='value'
    store.set('NOTSIP_TEST_SECRET','')
    assert store.get('NOTSIP_TEST_SECRET') is None

def test_browser_toggle_is_enforced(monkeypatch):
    monkeypatch.setattr(settings, 'browser_enabled', False)
    with pytest.raises(RuntimeError, match='browser automation is disabled'):
        asyncio.run(Browser().extract('https://example.com'))

def test_voice_and_screen_toggles_exist():
    assert hasattr(settings, 'voice_enabled')
    assert hasattr(settings, 'native_voice_enabled')
    assert hasattr(settings, 'perception_screen_enabled')

def test_oidc_pending_state_is_durable(tmp_path):
    local_settings=settings.model_copy(deep=True)
    a=AuthManager(local_settings,tmp_path)
    a.sessions['oidc:test']={'verifier':'v','nonce':'n','expires':time.time()+600}
    b=AuthManager(local_settings,tmp_path)
    assert b.sessions.get('oidc:test')['verifier']=='v'
    assert b.sessions.pop('oidc:test')['nonce']=='n'
