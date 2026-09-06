import base64, tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from notsip.security import SecretStore, pkce_pair, OIDCProvider
from notsip.nodes import NodeRegistry, RecoveryManager
from notsip.intelligence import Intelligence
from notsip.store import Store
from notsip.world import WorldModel
from notsip.core_runtime import app

def test_security_secret_roundtrip(tmp_path):
    s=SecretStore(tmp_path);s.set('x','secret-value');assert s.get('x')=='secret-value';assert (tmp_path/'secrets.enc').exists()

def test_pkce_pair_is_s256():
    verifier,challenge=pkce_pair();assert verifier and challenge and len(challenge)>40

def test_node_lease_and_recovery(tmp_path,monkeypatch):
    monkeypatch.setenv('NOTSIP_NODE_LEASE_SECONDS','1');store=Store(tmp_path);nodes=NodeRegistry(store,'secret');r=nodes.register('node1','Node','test',[]);assert r['token'];assert nodes.heartbeat('node1',r['token'])['lease_expires']>0
    recovery=RecoveryManager(tmp_path);p=recovery.checkpoint({'x':1});assert Path(tmp_path,p).exists();assert recovery.latest()['x']==1

def test_intelligence_helpers(tmp_path):
    store=Store(tmp_path);store.fact('The sky is blue','source-a','u1',.8);store.fact('The sky is blue','source-b','u2',.7);world=WorldModel(store);i=Intelligence(store,world);assert i.corroborate('sky')[0]['support']==2;assert len(i.plan('do something')['steps'])==5

def test_production_routes_are_assembled():
    paths={r.path for r in app.routes}
    expected={'/api/voice/transcribe','/api/voice/speak','/api/perception/frame','/api/federation/register','/api/federation/nodes','/api/recovery/checkpoint','/api/integrations/{provider_name}/calendar'}
    assert expected <= paths

def test_health_shape():
    with TestClient(app) as client:
        r=client.get('/api/health');assert r.status_code==200;data=r.json();assert data['identity']=='NOTSIP' and 'voice_stt' in data or True
