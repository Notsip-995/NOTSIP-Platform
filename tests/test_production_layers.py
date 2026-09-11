from pathlib import Path
from types import SimpleNamespace
from datetime import datetime
from fastapi.testclient import TestClient
from notsip.security import SecretStore, pkce_pair
from notsip.nodes import NodeRegistry, RecoveryManager
from notsip.intelligence import Intelligence
from notsip.store import Store
from notsip.world import WorldModel
from notsip.agent import Agent
from notsip.policy import Policy
from notsip.tools import Registry
from notsip.memory_service import MemoryService
from notsip.config import settings
from notsip.core_runtime import app
import asyncio

def test_security_secret_roundtrip(tmp_path):
    s=SecretStore(tmp_path);s.set('x','secret-value');assert s.get('x')=='secret-value';assert (tmp_path/'secrets.enc').exists()

def test_secret_clear_is_authoritative(tmp_path):
    s=SecretStore(tmp_path);s.set('x','secret-value');s.set('x','');assert s.get('x') is None

def test_pkce_pair_is_s256():
    verifier,challenge=pkce_pair();assert verifier and challenge and len(challenge)>40

def test_node_lease_and_recovery(tmp_path,monkeypatch):
    monkeypatch.setenv('NOTSIP_NODE_LEASE_SECONDS','1');store=Store(tmp_path);nodes=NodeRegistry(store,'secret');nonce='n1';sig=nodes.sign('node1',nonce);r=nodes.register('node1','Node','test',[],nonce=nonce,signature=sig);assert r['token'];beat_nonce='n2';beat_sig=nodes.sign('node1',beat_nonce);assert nodes.heartbeat('node1',r['token'],nonce=beat_nonce,signature=beat_sig)['lease_expires']>0
    recovery=RecoveryManager(tmp_path);p=recovery.checkpoint({'tasks':[],'devices':[],'world':{'entities':[],'relations':[],'facts':[]}});assert Path(tmp_path,p).exists();assert recovery.latest()['tasks']==[];assert recovery.verify_latest()['valid']

def test_recovery_restore_applies_runtime_state(tmp_path):
    store=Store(tmp_path);store.task('old task');recovery=RecoveryManager(tmp_path);recovery.checkpoint({'tasks':[{'id':'restored','objective':'restored task','state':'PENDING','priority':1,'handler':'agent','data':{},'run_at':0,'interval_sec':None,'retries':0,'created':1,'updated':1,'error':''}],'devices':[],'world':{'entities':[],'relations':[],'facts':[]}});result=store.restore_runtime_state(recovery.latest());assert result['status']=='RESTORED';assert [x['id'] for x in store.tasks()] == ['restored']

def test_recovery_preserves_device_token_hash(tmp_path):
    store=Store(tmp_path);token='device-secret';store.pair_device('android-1','Phone','android','',token)
    snapshot={'tasks':[],'devices':store.rows('SELECT id,name,platform,public_key,token_hash,last_seen,status,data FROM devices'),'world':{'entities':[],'relations':[],'facts':[]}}
    result=store.restore_runtime_state(snapshot);assert result['status']=='RESTORED';assert store.device_token_valid('android-1',token);assert not store.device_token_valid('android-1','wrong-token')

def test_agent_audit_paths_write_valid_records(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'data_dir',str(tmp_path));monkeypatch.setattr(settings,'llm_base_url','');monkeypatch.setattr(settings,'llm_model','');monkeypatch.setattr(settings,'llm_api_key','');monkeypatch.setattr(settings,'fallback_llm_base_url','');monkeypatch.setattr(settings,'fallback_llm_model','');monkeypatch.setattr(settings,'fallback_llm_api_key','');monkeypatch.setattr(settings,'autonomy_level',2)
    store=Store(tmp_path);registry=Registry();world=WorldModel(store);provider=SimpleNamespace(enabled=False,fallback_enabled=False);agent=Agent(settings,store,Policy(2),registry,provider,world)
    result=asyncio.run(agent.handle('status'));assert result['status']=='DEGRADED';rows=store.audit_recent(10);assert rows and len(rows[0])>=6
    async_result=asyncio.run(agent.run_tool('missing',{}));assert async_result['status']=='FAILURE'

def test_intelligence_helpers(tmp_path):
    store=Store(tmp_path);store.fact('The sky is blue','source-a','u1',.8);store.fact('The sky is blue','source-b','u2',.7);world=WorldModel(store);i=Intelligence(store,world);assert i.corroborate('sky')[0]['support']==2;assert len(i.plan('do something')['steps'])==5

def test_intelligence_does_not_count_same_source_as_independent(tmp_path):
    store=Store(tmp_path)
    store.fact('Server latency is high','same-source','u1',.8)
    store.fact('Server latency is high','same-source','u2',.9)
    store.fact('Server latency is high','second-source','u3',.7)
    i=Intelligence(store,WorldModel(store));f=i.corroborate('latency')[0]
    assert f['support']==3
    assert f['independent_sources']==2
    assert f['sources']==['same-source','second-source']
    assert f['best_source_confidence']==.9
    assert f['corroboration_score']==.7

def test_memory_consolidation_removes_duplicates(tmp_path):
    store=Store(tmp_path);memory=MemoryService(store,'u')
    memory.remember('Important fact',weight=.8);memory.remember(' important   fact ',weight=.6);memory.remember('Other fact',weight=.7)
    result=memory.consolidate()
    assert result['examined']==3 and result['unique']==2 and result['duplicates_removed']==1
    rows=store.rows('SELECT content FROM memories WHERE user_id=? ORDER BY weight DESC',('u',))
    assert [r['content'] for r in rows]==['Important fact','Other fact']
    memory.remember('Important fact',kind='procedural',weight=.5)
    result=memory.consolidate()
    assert result['duplicates_removed']==0
    assert store.rows('SELECT kind FROM memories WHERE user_id=? AND content=?',('u','Important fact'))

def test_agent_clock_uses_configured_timezone(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'data_dir',str(tmp_path));monkeypatch.setattr(settings,'local_timezone','Africa/Kigali')
    store=Store(tmp_path);agent=Agent(settings,store,Policy(2),Registry(),SimpleNamespace(enabled=False,fallback_enabled=False),WorldModel(store))
    result=asyncio.run(agent.handle('what time is it'));assert result['status']=='SUCCESS';assert 'Africa/Kigali' in result['response'];assert 'UTC' in result['response']
    result=asyncio.run(agent.handle('what time is it in Tokyo'));assert result['status']=='SUCCESS';assert 'JST' in result['response']

def test_agent_relative_dates(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'data_dir',str(tmp_path));monkeypatch.setattr(settings,'local_timezone','Africa/Kigali')
    agent=Agent(settings,Store(tmp_path),Policy(2),Registry(),SimpleNamespace(enabled=False,fallback_enabled=False),WorldModel(Store(tmp_path)))
    tomorrow=asyncio.run(agent.handle('what date is tomorrow'))['response']
    next_monday=asyncio.run(agent.handle('what is next monday'))['response']
    two_weeks=asyncio.run(agent.handle('what date is in two weeks'))['response']
    assert 'Tomorrow is ' in tomorrow
    assert 'Next Monday is ' in next_monday
    assert 'In two weeks it will be ' in two_weeks

def test_agent_clock_context_exposes_utc_and_timezone(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'data_dir',str(tmp_path));monkeypatch.setattr(settings,'local_timezone','Africa/Kigali')
    store=Store(tmp_path);agent=Agent(settings,store,Policy(2),Registry(),SimpleNamespace(enabled=False,fallback_enabled=False),WorldModel(store));ctx=agent.context('hello')
    assert ctx['timezone']=='Africa/Kigali';assert datetime.fromisoformat(ctx['utc_time']).tzinfo is not None

def test_production_routes_are_assembled():
    paths={r.path for r in app.routes};expected={'/api/voice/transcribe','/api/voice/speak','/api/perception/frame','/api/federation/register','/api/federation/nodes','/api/recovery/checkpoint','/api/integrations/{provider_name}/calendar','/api/update/check','/api/sessions','/api/memory/maintain','/api/diagnostics','/api/backups/{name}/restore'};assert expected <= paths

def test_health_shape():
    with TestClient(app) as client:
        r=client.get('/api/health');assert r.status_code==200;data=r.json();assert data['identity']=='NOTSIP' and 'voice_stt' in data
