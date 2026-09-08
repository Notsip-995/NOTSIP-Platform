import pytest
from notsip.config import Settings


def test_sensitive_config_fields_are_classified_for_approval():
    from notsip import app
    assert 'api_key' in app.CONFIG_HIGH_RISK
    assert 'node_shared_secret' in app.CONFIG_HIGH_RISK
    assert 'llm_api_key' in app.CONFIG_SECRET_NAMES


def test_invalid_remote_security_posture_is_rejected_transactionally(tmp_path):
    s=Settings(host='127.0.0.1',data_dir=str(tmp_path),auth_mode='api_key',api_key='safe-key')
    snapshot=s.host
    s.host='0.0.0.0';s.api_key=''
    with pytest.raises(RuntimeError,match='Remote binding requires'):
        s.ensure()
    s.host=snapshot;s.api_key='safe-key';s.ensure()


def test_remote_oidc_requires_issuer_client_and_redirect(tmp_path):
    s=Settings(host='0.0.0.0',data_dir=str(tmp_path),auth_mode='oidc',oidc_issuer='https://issuer.example',oidc_client_id='',oidc_redirect_uri='')
    with pytest.raises(RuntimeError,match='Remote binding with OIDC requires'):
        s.ensure()


def test_execution_gate_is_rebound_to_new_runtime_policy(monkeypatch,tmp_path):
    from notsip import app
    from notsip.execution_gate import ToolExecutionGate
    from notsip.policy import Policy
    old_level=app.settings.autonomy_level
    old_caps=dict(app.settings.capability_levels)
    old_policy=app.policy
    try:
        app.settings.autonomy_level=1
        app.settings.capability_levels={'TEST_CAP':1}
        app._rebuild_runtime_after_config()
        assert ToolExecutionGate._policy is app.policy
        assert ToolExecutionGate._policy.level==1
    finally:
        app.settings.autonomy_level=old_level
        app.settings.capability_levels=old_caps
        app.policy=old_policy
        ToolExecutionGate.configure(old_policy,app.agent.approvals)
