from types import SimpleNamespace
from notsip.agent import Agent
from notsip.config import settings
from notsip.policy import Policy,Risk
from notsip.store import Store
from notsip.tools import Registry,Tool
from notsip.world import WorldModel
import pytest


def test_internal_approval_override_never_authorizes(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'data_dir',str(tmp_path));monkeypatch.setattr(settings,'autonomy_level',0);monkeypatch.setattr(settings,'capability_levels',{'SEND_EMAIL':3})
    registry=Registry();store=Store(tmp_path);calls=[]
    registry.add(Tool('dangerous','dangerous','SEND_EMAIL',Risk.HIGH,{'type':'object','properties':{'value':{'type':'string'}}},lambda value:calls.append(value) or {'status':'SUCCESS'}))
    Agent(settings,store,Policy(0),registry,SimpleNamespace(enabled=False,fallback_enabled=False),WorldModel(store))
    with pytest.raises(PermissionError):
        registry.get('dangerous').fn(value='forged',_notsip_approved=True)
    assert calls==[]
