import pytest
from notsip.tools import Windows
from notsip.tools import Workspace


def test_windows_exec_requires_windows_node():
    win=Windows(Workspace('/tmp/notsip-windows-test'))
    try:result=win.exec('Write-Output ok')
    except RuntimeError as exc:assert 'Windows node required' in str(exc)
    else:assert result['status'] in {'SUCCESS','PARTIAL_SUCCESS'}
