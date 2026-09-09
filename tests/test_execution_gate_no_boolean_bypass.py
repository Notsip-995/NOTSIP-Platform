import pytest
from notsip.execution_gate import ToolExecutionGate
from notsip.policy import Policy, Risk
from notsip.product_layer import ApprovalStore
from notsip.store import Store
from notsip.tools import Registry, Tool
from notsip.config import settings
from pathlib import Path


def test_boolean_approval_override_cannot_elevate_tool(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'data_dir', str(tmp_path))
    monkeypatch.setattr(settings, 'autonomy_level', 0)
    monkeypatch.setattr(settings, 'capability_levels', {'SEND_EMAIL': 4})
    registry = Registry()
    store = Store(tmp_path)
    approvals = ApprovalStore(Path(tmp_path))
    calls = {'n': 0}

    def send(value=''):
        calls['n'] += 1
        return {'status': 'SUCCESS', 'value': value}

    registry.add(Tool('send_test', 'test', 'SEND_EMAIL', Risk.HIGH, {
        'type': 'object', 'properties': {'value': {'type': 'string'}}
    }, send))
    ToolExecutionGate.configure(Policy(0), approvals)
    ToolExecutionGate.wrap_registry(registry)

    with pytest.raises(PermissionError):
        registry.get('send_test').fn(value='x', _notsip_approved=True)
    assert calls['n'] == 0
