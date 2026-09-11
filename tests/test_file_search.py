from notsip.system_services import _search_workspace
from notsip.tools import Workspace


def test_workspace_search_uses_content_not_only_filename(tmp_path):
    ws=Workspace(tmp_path)
    ws.write('minutes.txt','The architecture review with Sarah is on Thursday.')
    ws.write('random.md','nothing relevant')
    result=_search_workspace(ws,'Sarah')
    assert result['status']=='SUCCESS'
    assert result['results'][0]['path']=='minutes.txt'
    assert 'Sarah' in result['results'][0]['snippet']
