from pathlib import Path
from tempfile import TemporaryDirectory
from notsip import system_services


def test_time_snapshot_has_timezone_and_iso():
    snap=system_services._time_snapshot()
    assert snap['timezone']
    assert 'T' in snap['iso']
    assert snap['date'] and snap['time']
    assert snap['utc'].endswith('Z')


def test_workspace_file_operations_are_authorized():
    with TemporaryDirectory() as d:
        ws=system_services.Workspace(Path(d))
        ws.write('a.txt','hello')
        assert system_services._copy(ws,'a.txt','b.txt')['status']=='SUCCESS'
        assert ws.path('b.txt').read_text()=='hello'
        assert system_services._move(ws,'b.txt','c.txt')['status']=='SUCCESS'
        assert system_services._rename(ws,'c.txt','d.txt')['status']=='SUCCESS'
        assert system_services._archive(ws,['a.txt','d.txt'],'x.zip')['status']=='SUCCESS'
        assert system_services._delete(ws,'d.txt')['status']=='SUCCESS'


def test_python_execution_fails_closed_without_isolated_sandbox(monkeypatch):
    monkeypatch.delenv('NOTSIP_CODE_SANDBOX',raising=False)
    monkeypatch.delenv('NOTSIP_ALLOW_UNSAFE_CODE_EXEC',raising=False)
    with TemporaryDirectory() as d:
        ws=system_services.Workspace(Path(d));result=system_services._python_exec(ws,'print(2 + 3)')
        assert result['status']=='BLOCKED_BY_EXTERNAL_ENVIRONMENT'


def test_python_execution_can_be_explicitly_enabled_for_local_development(monkeypatch):
    monkeypatch.setenv('NOTSIP_CODE_SANDBOX','local-unsafe')
    monkeypatch.setenv('NOTSIP_ALLOW_UNSAFE_CODE_EXEC','true')
    with TemporaryDirectory() as d:
        ws=system_services.Workspace(Path(d));result=system_services._python_exec(ws,'print(2 + 3)')
        assert result['status']=='SUCCESS'
        assert result['stdout'].strip()=='5'
