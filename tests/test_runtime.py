from fastapi.testclient import TestClient
from notsip.core_runtime import app
from notsip.config import settings
import notsip.app as app_module
import notsip.runtime_prod as runtime_prod


def _client_with_auth():
    client=TestClient(app)
    headers={}
    if getattr(settings,'api_key',''):
        login=client.post('/api/login',json={'api_key':settings.api_key})
        assert login.status_code==200, login.text
        headers['Authorization']='Bearer '+settings.api_key
    return client,headers


def test_product_ui_and_setup_routes():
    with TestClient(app) as c:
        r=c.get('/')
        assert r.status_code in (200,302)
        if r.status_code==200: assert 'NOTSIP' in r.text
        s=c.get('/setup')
        assert s.status_code==200 and 'first-run setup' in s.text.lower()


def test_product_control_plane():
    c,headers=_client_with_auth()
    try:
        for path in ['/api/health','/api/status','/api/degraded','/api/capabilities','/api/diagnostics','/api/approvals','/api/backups','/api/devices','/api/tasks','/api/self/provenance','/api/sessions','/api/integrations/accounts','/api/update/check']:
            r=c.get(path,headers=headers);assert r.status_code in (200,503), (path,r.text)
    finally:c.close()


def test_backup_roundtrip_and_process_info():
    c,headers=_client_with_auth()
    try:
        b=c.post('/api/backups',headers=headers);assert b.status_code==200;assert b.json()['status']=='SUCCESS'
        v=c.get('/api/backups',headers=headers).json();assert v['backups'];name=v['backups'][0]['name'];chk=c.get('/api/backups/'+name+'/verify',headers=headers);assert chk.status_code==200 and chk.json()['valid']
        p=c.get('/api/process',headers=headers).json();assert p['pid']>0
    finally:c.close()


def test_login_session_cookie():
    with TestClient(app) as c:
        if settings.api_key:
            unauthorized=c.get('/api/health');assert unauthorized.status_code==401
            r=c.post('/api/login',json={'api_key':settings.api_key});assert r.status_code==200;assert 'notsip_session' in r.cookies
            authorized=c.get('/api/health',headers={'Authorization':'Bearer '+settings.api_key});assert authorized.status_code==200
        else:
            r=c.get('/api/health');assert r.status_code==200


def test_canonical_runtime_reuses_authoritative_instances():
    assert runtime_prod.store is app_module.store
    assert runtime_prod.provider is app_module.provider
    assert runtime_prod.policy is app_module.policy
    assert runtime_prod.agent is app_module.agent
    assert runtime_prod.registry is app_module.registry
    assert runtime_prod.auth is app_module.auth
    assert runtime_prod.nodes is app_module.nodes
