import json
from pathlib import Path
from types import SimpleNamespace
from notsip.agent import Agent
from notsip.connectors import _public_host
from notsip.policy import Policy,Risk
from notsip.product_layer import ConfigStore
from notsip.security import SecretStore
from notsip.store import Store
from notsip.tools import Registry,Tool
from notsip.world import WorldModel
from notsip.config import settings
import asyncio

def test_public_host_rejects_private_and_loopback_literals():
    for host in ('127.0.0.1','localhost','10.0.0.1','192.168.1.1','169.254.169.254','::1'): assert _public_host(host) is False

def test_config_store_never_persists_protected_database_url(tmp_path):
    c=ConfigStore(tmp_path);c.save({'host':'127.0.0.1','database_url':'postgresql://user:password@example/db'});raw=json.loads((Path(tmp_path)/'config.json').read_text());assert 'database_url' not in raw['settings']

def test_secret_store_database_url_roundtrip(tmp_path):
    s=SecretStore(tmp_path);s.set('NOTSIP_DATABASE_URL','postgresql://user:password@example/db');assert s.get('NOTSIP_DATABASE_URL')=='postgresql://user:password@example/db';s.set('NOTSIP_DATABASE_URL','');assert s.get('NOTSIP_DATABASE_URL') is None

def test_capability_level_is_enforced(monkeypatch):
    monkeypatch.setattr(settings,'autonomy_level',2);monkeypatch.setattr(settings,'capability_levels',{'CONTROL_COMPUTER':3});decision=Policy(2).decide(Risk.LOW,False,'CONTROL_COMPUTER');assert not decision.allowed;assert decision.needs_confirmation;assert decision.required_level==3

def test_agent_records_capability_requirement_in_approval(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'data_dir',str(tmp_path));monkeypatch.setattr(settings,'autonomy_level',2);monkeypatch.setattr(settings,'capability_levels',{'TEST_CAP':3});registry=Registry();store=Store(tmp_path);registry.add(Tool('test_tool','test','TEST_CAP',Risk.LOW,{'type':'object','properties':{}},lambda:{'status':'SUCCESS'}));agent=Agent(settings,store,Policy(2),registry,SimpleNamespace(enabled=False,fallback_enabled=False),WorldModel(store));result=asyncio.run(agent.run_tool('test_tool',{}));assert result['status']=='PARTIAL_SUCCESS';assert result['approval_required'];assert result['capability']=='TEST_CAP';assert result['required_level']==3

def test_approved_tool_can_elevate_noncritical_capability(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'data_dir',str(tmp_path));monkeypatch.setattr(settings,'autonomy_level',2);monkeypatch.setattr(settings,'capability_levels',{'SEND_EMAIL':3});registry=Registry();store=Store(tmp_path);calls=[];registry.add(Tool('dangerous','dangerous','SEND_EMAIL',Risk.HIGH,{'type':'object','properties':{'value':{'type':'string'}}},lambda value:calls.append(value) or {'status':'SUCCESS'}));agent=Agent(settings,store,Policy(2),registry,SimpleNamespace(enabled=False,fallback_enabled=False),WorldModel(store));pending=asyncio.run(agent.run_tool('dangerous',{'value':'approved-value'}));assert pending['status']=='PARTIAL_SUCCESS';agent.approvals.decide(pending['approval_id'],True);result=registry.get('dangerous').fn(value='approved-value');assert result['status']=='SUCCESS';assert calls==['approved-value'];assert agent.approvals._load()[pending['approval_id']]['status']=='EXECUTED'

def test_approved_tool_args_must_match_exactly(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'data_dir',str(tmp_path));monkeypatch.setattr(settings,'autonomy_level',2);monkeypatch.setattr(settings,'capability_levels',{'SEND_EMAIL':2});registry=Registry();store=Store(tmp_path);calls=[];registry.add(Tool('dangerous','dangerous','SEND_EMAIL',Risk.HIGH,{'type':'object','properties':{'value':{'type':'string'}}},lambda value:calls.append(value) or {'status':'SUCCESS'}));agent=Agent(settings,store,Policy(2),registry,SimpleNamespace(enabled=False,fallback_enabled=False),WorldModel(store));pending=asyncio.run(agent.run_tool('dangerous',{'value':'approved-value'}));agent.approvals.decide(pending['approval_id'],True)
    try:registry.get('dangerous').fn(value='different-value')
    except PermissionError:pass
    else:raise AssertionError('mismatched arguments must not consume approval')
    assert calls==[]

def test_failed_approved_action_is_not_left_executing(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'data_dir',str(tmp_path));monkeypatch.setattr(settings,'autonomy_level',2);monkeypatch.setattr(settings,'capability_levels',{'SEND_EMAIL':2});registry=Registry();store=Store(tmp_path)
    def fail(value): raise RuntimeError('tool failed')
    registry.add(Tool('dangerous','dangerous','SEND_EMAIL',Risk.HIGH,{'type':'object','properties':{'value':{'type':'string'}}},fail));agent=Agent(settings,store,Policy(2),registry,SimpleNamespace(enabled=False,fallback_enabled=False),WorldModel(store));pending=asyncio.run(agent.run_tool('dangerous',{'value':'fail'}));agent.approvals.decide(pending['approval_id'],True)
    try:registry.get('dangerous').fn(value='fail')
    except RuntimeError:pass
    else:raise AssertionError('failing approved action must propagate its failure')
    assert agent.approvals._load()[pending['approval_id']]['status']=='FAILED'
