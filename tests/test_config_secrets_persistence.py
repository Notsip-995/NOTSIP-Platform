"""Regression tests: secret/config saves must persist at autonomy 2 for the human admin.

Covers two 0.9.0 wizard bugs:
1. Secret fields were routed through the approval-gated config_admin tool, so at
   autonomy < 4 a save returned approval_required and nothing persisted.
2. After changing api_key through a bootstrap save, the running runtime still
   authenticated with the old key because app._rebuild_runtime_after_config
   updated app's imported copy of auth_token instead of runtime_prod's module global.

All tests patch module globals with monkeypatch (auto-restored) and redirect the
config store + secret store into tmp_path so no state leaks between tests.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from notsip import app as app_module
import notsip.runtime_prod as runtime_prod
from notsip.config import Settings
from notsip.product_layer import ConfigStore
from notsip.security import SecretStore, DurableState
from notsip.execution_gate import ToolExecutionGate


@pytest.fixture
def hermetic(tmp_path, monkeypatch):
    """Redirect config/secret stores and settings to a throwaway dir."""

    def _setup(**overrides):
        base = dict(host='127.0.0.1', data_dir=str(tmp_path),
                    auth_mode='api_key', api_key='primary-test-key',
                    autonomy_level=2)
        base.update(overrides)
        s = Settings(**base)
        monkeypatch.setattr(app_module, 'settings', s)
        cs = ConfigStore(Path(tmp_path))
        monkeypatch.setattr(app_module, 'config_store', cs)
        secret_store = SecretStore(Path(tmp_path))
        auth = SimpleNamespace(
            secrets=secret_store,
            sessions=DurableState(secret_store),
            settings=s, oidc=None,
            mint_session=lambda claims: 'sess-token',
            validate_session=lambda tok: True,
        )
        monkeypatch.setattr(app_module, 'auth', auth)
        return s, cs, auth

    return _setup


def test_secret_names_are_high_risk_but_human_save_bypasses_pending_gate(tmp_path, monkeypatch, hermetic):
    """The authenticated primary admin persists secrets directly at autonomy 2."""
    settings, cs, auth = hermetic()
    requested = {'llm_api_key': 'sk-save', 'pairing_secret': 'pair-save'}
    result = app_module._apply_config(requested, bootstrap=False)
    assert result['status'] == 'SUCCESS'
    assert set(result['changed']) == set(requested)
    # persisted immediately; not parked in a pending record for config_admin
    assert auth.secrets.get('NOTSIP_LLM_API_KEY') == 'sk-save'
    assert auth.secrets.get('NOTSIP_PAIRING_SECRET') == 'pair-save'
    assert auth.secrets.get('config:pending::0') is None
    # agent-driven approval path must still exist
    assert app_module.registry.get('config_admin') is not None


def test_non_bootstrap_secret_save_marks_restart_and_persists(tmp_path, hermetic):
    settings, cs, auth = hermetic()
    result = app_module._apply_config({'brave_api_key': 'brave-x'}, bootstrap=False)
    assert result['status'] == 'SUCCESS'
    assert result['restart_required'] is True
    assert auth.secrets.get('NOTSIP_BRAVE_API_KEY') == 'brave-x'


def test_bootstrap_save_syncs_runtime_prod_auth_token(tmp_path, monkeypatch, hermetic):
    """After a bootstrap api_key change the live runtime authenticates with the new key."""
    # snapshot the real singleton objects BEFORE patching them
    real_policy = app_module.policy
    real_agent = app_module.agent
    real_oidc = app_module.auth.oidc
    settings, cs, auth = hermetic(api_key='old-key')
    # isolate every object _rebuild_runtime_after_config touches
    fake_nodes = SimpleNamespace(secret=None)
    fake_agent = SimpleNamespace(provider=None, policy=None, approvals=[])
    monkeypatch.setattr(app_module, 'nodes', fake_nodes)
    monkeypatch.setattr(app_module, 'agent', fake_agent)
    monkeypatch.setattr(app_module, 'provider', None)
    monkeypatch.setattr(app_module, 'web', None)
    monkeypatch.setattr(app_module, 'emailc', None)
    monkeypatch.setattr(app_module, 'policy', None)
    monkeypatch.setattr(app_module, 'diagnostics', None)
    monkeypatch.setattr(app_module, 'probes', None)
    monkeypatch.setattr(app_module, 'auth_token', 'old-key', raising=False)
    monkeypatch.setattr(runtime_prod, 'auth_token', 'old-key')
    monkeypatch.setattr(runtime_prod, 'auth', auth)
    monkeypatch.setattr(runtime_prod, 'provider', None)
    monkeypatch.setattr(runtime_prod, 'web', None)
    monkeypatch.setattr(runtime_prod, 'emailc', None)
    monkeypatch.setattr(runtime_prod, 'policy', None)
    try:
        app_module._apply_config({'api_key': 'new-key'}, bootstrap=True)
        assert runtime_prod.auth_token == 'new-key'
        assert settings.api_key == 'new-key'
    finally:
        # restore the gate to the canonical policy + real approvals store so
        # later tests see approval-gated behavior unchanged
        app_module.auth.oidc = real_oidc
        ToolExecutionGate.configure(real_policy, real_agent.approvals)


def test_api_key_session_is_primary_actor(monkeypatch):
    """A session minted with mode='api_key' must resolve to the primary admin.

    Regression: actor_context._safe_actor treated every session as OIDC, mapping
    sub='primary-user' to 'oidc:primary-user', so config_set_hardened answered 403
    to the wizard's own authenticated saves after the initial bootstrap.
    """
    from notsip.actor_context import _safe_actor
    assert _safe_actor({'mode': 'api_key', 'sub': 'primary-user'}) == 'primary-user'
    # OIDC sessions keep scoped identities and never claim primary admin.
    assert _safe_actor({'iss': 'https://idp.example', 'sub': 'alice@example.com'}) == 'https://idp.example:alice@example.com'


def test_config_admin_gate_preserved_for_agent_changes(tmp_path, monkeypatch):
    """config_admin remains approval-gated at autonomy < 4 (agent path unchanged)."""
    tool = app_module.registry.get('config_admin')
    assert tool is not None
    with pytest.raises(PermissionError, match='requires autonomy level 4'):
        tool.fn(pending_id='nope', keys=['llm_api_key'])


def test_public_state_redacts_secrets_but_reports_configured(tmp_path, hermetic):
    from notsip.setup_hardening import _public_state
    settings, cs, auth = hermetic()
    app_module.auth.secrets.set('NOTSIP_LLM_API_KEY', 'sk-hidden')
    state = _public_state(app_module)
    assert state['secret_configured']['llm_api_key'] is True
    blob = __import__('json').dumps(state['settings'])
    assert 'sk-hidden' not in blob
    assert 'llm_api_key' not in state['settings']