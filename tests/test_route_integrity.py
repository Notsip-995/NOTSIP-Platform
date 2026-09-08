from fastapi.testclient import TestClient
from notsip.core_runtime import app
from notsip.config import settings


def test_route_inventory_contains_expected_protected_surface():
    paths={r.path for r in app.routes}
    assert '/api/windows/click' in paths
    assert '/api/files/delete' in paths
    assert '/api/integrations/accounts/{account_id}/disconnect' in paths


def test_direct_windows_api_cannot_bypass_capability_policy(monkeypatch):
    monkeypatch.setattr(settings,'autonomy_level',2)
    monkeypatch.setattr(settings,'capability_levels',{'CONTROL_COMPUTER':3})
    with TestClient(app) as client:
        response=client.get('/api/windows/tree')
    assert response.status_code==403
    body=response.json()
    assert body['capability']=='CONTROL_COMPUTER'
    assert body['required_level']==3


def test_direct_file_delete_cannot_bypass_capability_policy(monkeypatch):
    monkeypatch.setattr(settings,'autonomy_level',2)
    monkeypatch.setattr(settings,'capability_levels',{'WRITE_FILES':3})
    with TestClient(app) as client:
        response=client.post('/api/files/delete',json={'path':'does-not-exist.txt'})
    assert response.status_code==403
    assert response.json()['capability']=='WRITE_FILES'
