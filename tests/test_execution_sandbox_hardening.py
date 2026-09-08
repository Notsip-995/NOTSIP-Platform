from pathlib import Path


def test_execution_sandbox_blocks_without_docker(monkeypatch, tmp_path):
    from notsip.execution_sandbox import ExecutionSandbox
    monkeypatch.setattr('shutil.which', lambda _: None)
    result = ExecutionSandbox(Path(tmp_path)).run_python('print(1)')
    assert result['status'] == 'BLOCKED'
    assert result['verified'] is False


def test_execution_tool_is_high_risk_and_capability_bound():
    from notsip.policy import Risk
    from notsip.core_runtime import registry
    tool = registry.get('execute_python')
    assert tool is not None
    assert tool.risk == Risk.HIGH
    assert tool.capability == 'EXECUTE_CODE'
    assert tool.destructive is True
