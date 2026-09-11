from types import SimpleNamespace
from notsip.agent import Agent
from notsip.config import settings
from notsip.policy import Policy,Risk
from notsip.store import Store
from notsip.tools import Registry,Tool
from notsip.world import WorldModel
import pytest
import time


def _agent(tmp_path,autonomy=0,capability_level=3):
    settings.data_dir=str(tmp_path)
    settings.autonomy_level=autonomy
    settings.capability_levels={'SEND_EMAIL':capability_level}
    registry=Registry();store=Store(tmp_path);calls=[]
    registry.add(Tool('dangerous','dangerous','SEND_EMAIL',Risk.HIGH,{'type':'object','properties':{'value':{'type':'string'}}},lambda value:calls.append(value) or {'status':'SUCCESS'}))
    agent=Agent(settings,store,Policy(autonomy),registry,SimpleNamespace(enabled=False,fallback_enabled=False),WorldModel(store))
    return agent,registry,calls


def test_internal_approval_override_never_authorizes(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'data_dir',str(tmp_path));monkeypatch.setattr(settings,'autonomy_level',0);monkeypatch.setattr(settings,'capability_levels',{'SEND_EMAIL':3})
    registry=Registry();store=Store(tmp_path);calls=[]
    registry.add(Tool('dangerous','dangerous','SEND_EMAIL',Risk.HIGH,{'type':'object','properties':{'value':{'type':'string'}}},lambda value:calls.append(value) or {'status':'SUCCESS'}))
    Agent(settings,store,Policy(0),registry,SimpleNamespace(enabled=False,fallback_enabled=False),WorldModel(store))
    with pytest.raises(PermissionError):
        registry.get('dangerous').fn(value='forged',_notsip_approved=True)
    assert calls==[]


def test_approved_action_honors_persisted_expiration(tmp_path,monkeypatch):
    agent,registry,calls=_agent(tmp_path,autonomy=0,capability_level=3)
    monkeypatch.setattr(settings,'data_dir',str(tmp_path))
    pending=agent.approvals.request('dangerous','test',{'tool':'dangerous','args':{'value':'x'},'actor':'primary-user'},ttl=900)
    decided=time.time();data=agent.approvals._load();data[pending['id']]['status']='APPROVED';data[pending['id']]['decided']=decided;data[pending['id']]['expires']=decided+120;agent.approvals._save(data)
    result=registry.get('dangerous').fn(value='x')
    assert result['status']=='SUCCESS'
    assert calls==['x']


def test_expired_approved_action_is_not_executed(tmp_path,monkeypatch):
    agent,registry,calls=_agent(tmp_path,autonomy=0,capability_level=3)
    pending=agent.approvals.request('dangerous','test',{'tool':'dangerous','args':{'value':'x'},'actor':'primary-user'},ttl=900)
    data=agent.approvals._load();data[pending['id']]['status']='APPROVED';data[pending['id']]['decided']=time.time();data[pending['id']]['expires']=time.time()-1;agent.approvals._save(data)
    with pytest.raises(PermissionError):registry.get('dangerous').fn(value='x')
    assert calls==[]
