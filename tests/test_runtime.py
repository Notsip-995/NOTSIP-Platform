from fastapi.testclient import TestClient
from notsip.core_runtime import app

def test_product_ui_and_setup_routes():
    with TestClient(app) as c:
        r=c.get('/');assert r.status_code==200 and 'NOTSIP' in r.text
        s=c.get('/setup');assert s.status_code==200 and 'first-run setup' in s.text.lower()

def test_product_control_plane():
    with TestClient(app) as c:
        for path in ['/api/health','/api/status','/api/degraded','/api/capabilities','/api/diagnostics','/api/approvals','/api/backups','/api/devices','/api/tasks','/api/self/provenance']:
            r=c.get(path);assert r.status_code==200,(path,r.text)

def test_backup_roundtrip_and_process_info():
    with TestClient(app) as c:
        b=c.post('/api/backups');assert b.status_code==200
        d=b.json();assert d['status']=='SUCCESS'
        v=c.get('/api/backups').json();assert v['backups']
        chk=c.get('/api/backups/'+v['backups'][0]['name']+'/verify');assert chk.status_code==200 and chk.json()['valid']
        p=c.get('/api/process').json();assert p['pid']>0
