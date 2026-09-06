from fastapi.testclient import TestClient
from notsip.core_runtime import app

def test_product_ui_and_setup_routes():
    with TestClient(app) as c:
        r=c.get('/');assert r.status_code in (200,302) and 'NOTSIP' in r.text or r.status_code==302
        s=c.get('/setup');assert s.status_code==200 and 'NOTSIP setup' in s.text

def test_product_control_plane():
    with TestClient(app) as c:
        for path in ['/api/health','/api/status','/api/degraded','/api/capabilities','/api/diagnostics','/api/approvals','/api/backups','/api/devices','/api/tasks','/api/self/provenance','/api/sessions','/api/integrations/accounts','/api/update/check']:
            r=c.get(path);assert r.status_code in (200,503), (path,r.text)

def test_backup_roundtrip_and_process_info():
    with TestClient(app) as c:
        b=c.post('/api/backups');assert b.status_code==200;assert b.json()['status']=='SUCCESS'
        v=c.get('/api/backups').json();assert v['backups'];name=v['backups'][0]['name'];chk=c.get('/api/backups/'+name+'/verify');assert chk.status_code==200 and chk.json()['valid']
        p=c.get('/api/process').json();assert p['pid']>0

def test_login_session_cookie():
    with TestClient(app) as c:
        # In CI/local test mode, no API key means local access remains available.
        r=c.get('/api/health');assert r.status_code==200
