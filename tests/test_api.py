from fastapi.testclient import TestClient
from notsip.core_runtime import app

def test_root_has_ui_or_json():
    with TestClient(app) as client:
        r=client.get('/')
        assert r.status_code==200

def test_health_and_status():
    with TestClient(app) as client:
        assert client.get('/api/health').json()['identity']=='NOTSIP'
        s=client.get('/api/status').json()
        assert 'devices' in s and 'tasks' in s and s['capabilities']['self_maintenance'] is True

def test_advertised_routes_exist():
    paths={r.path for r in app.routes}
    expected={'/api/degraded','/api/search','/api/email/status','/api/oauth/status','/api/tasks/{task_id}/run','/api/devices','/api/self/inspect','/api/self/verify','/api/self/read'}
    assert expected <= paths

def test_task_defaults_to_agent(tmp_path, monkeypatch):
    with TestClient(app) as client:
        r=client.post('/api/tasks',json={'objective':'say hello','handler':'agent'})
        assert r.status_code==200
        tid=r.json()['task_id']
        assert any(t['id']==tid and t['handler']=='agent' for t in client.get('/api/tasks').json()['tasks'])

def test_pairing_and_device_commands():
    with TestClient(app) as client:
        code=client.get('/api/pair/code').json()['code']
        paired=client.post('/api/pair/consume',json={'code':code,'device_id':'test-phone','name':'Test Phone','platform':'android'}).json()
        assert paired['token']
        assert client.get('/api/devices').json()['devices']
        q=client.post('/api/devices/test-phone/commands',json={'action':'notify','payload':{'text':'hello'}})
        assert q.status_code in (200,400)
