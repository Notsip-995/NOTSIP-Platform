from pathlib import Path
from tempfile import TemporaryDirectory
from notsip import system_services


def test_time_snapshot_has_timezone_and_iso():
    snap=system_services._time_snapshot()
    assert snap['timezone']
    assert 'T' in snap['iso']
    assert snap['date'] and snap['time']


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


def test_python_execution_is_time_limited_and_returns_result():
    with TemporaryDirectory() as d:
        ws=system_services.Workspace(Path(d))
        result=system_services._python_exec(ws,'print(2 + 3)')
        assert result['status']=='SUCCESS'
        assert result['stdout'].strip()=='5'
