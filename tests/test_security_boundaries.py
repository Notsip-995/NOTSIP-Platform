import json
from pathlib import Path
from types import SimpleNamespace
from notsip.agent import Agent
from notsip.connectors import _public_host
from notsip.policy import Policy,Risk
from notsip.product_layer import ConfigStore,ApprovalStore
from notsip.security import SecretStore
from notsip.store import Store
from notsip.tools import Registry,Tool
from notsip.world import WorldModel
from notsip.config import settings
import asyncio


def test_public_host_rejects_private_and_loopback_literals():
    for host in ('127.0.0.1','localhost','10.0.0.1','192.168.1.1','169.254.169.254','::1'):
        assert _public_host(host) is False


def test_config_store_never_persists_protected_database_url(tmp_path):
    c=ConfigStore(tmp_path)
    c.save({'host':'127.0.0.1','database_url':'postgresql://user:password@example/db'})
    raw=json.loads((Path(tmp_path)/'config.json').read_text())
    assert 'database_url' not in raw['settings']


def test_secret_store_database_url_roundtrip(tmp_path):
    s=SecretStore(tmp_path)
    s.set('NOTSIP_DATABASE_URL','postgresql://user:password@example/db')
    assert s.get('NOTSIP_DATABASE_URL')=='postgresql://user:password@example/db'
    s.set('NOTSIP_DATABASE_URL','')
    assert s.get('NOTSIP_DATABASE_URL') is None


def test_capability_level_is_enforced(monkeypatch):
    monkeypatch.setattr(settings,'autonomy_level',2)
    monkeypatch.setattr(settings,'capability_levels',{'CONTROL_COMPUTER':3})
    decision=Policy(2).decide(Risk.LOW,False,'CONTROL_COMPUTER')
    assert decision.allowed is False
    assert decision.needs_confirmation is True
    assert decision.required_level==3


def test_agent_records_capability_requirement_in_approval(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'data_dir',str(tmp_path));monkeypatch.setattr(settings,'autonomy_level',2);monkeypatch.setattr(settings,'capability_levels',{'TEST_CAP':3})
    registry=Registry();store=Store(tmp_path);registry.add(Tool('test_tool','test','TEST_CAP',Risk.LOW,{'type':'object','properties':{}},lambda:{'status':'SUCCESS'}))
    agent=Agent(settings,store,Policy(2),registry,SimpleNamespace(enabled=False,fallback_enabled=False),WorldModel(store))
    result=asyncio.run(agent.run_tool('test_tool',{}))
    assert result['status']=='PARTIAL_SUCCESS'
    assert result['approval_required'] is True
    assert result['capability']=='TEST_CAP'
    assert result['required_level']==3


def test_approved_tool_execution_still_passes_through_policy_gate(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'data_dir',str(tmp_path));monkeypatch.setattr(settings,'autonomy_level',2);monkeypatch.setattr(settings,'capability_levels',{'SEND_EMAIL':3})
    registry=Registry();store=Store(tmp_path);calls=[]
    registry.add(Tool('dangerous','dangerous','SEND_EMAIL',Risk.HIGH,{'type':'object','properties':{'value':{'type':'string'}}},lambda value:calls.append(value) or {'status':'SUCCESS'}))
    agent=Agent(settings,store,Policy(2),registry,SimpleNamespace(enabled=False,fallback_enabled=False),WorldModel(store))
    pending=asyncio.run(agent.run_tool('dangerous',{'value':'approved-value'}))
    approval=agent.approvals.decide(pending['approval_id'],True)
    assert approval['status']=='APPROVED'
    # Capability level 3 is still above current autonomy 2, so approval must not
    # manufacture permission for the capability itself.
    try: registry.get('dangerous').fn(value='approved-value')
    except PermissionError:
        pass
    else: raise AssertionError('approval must not bypass capability authorization')
    assert calls==[]
