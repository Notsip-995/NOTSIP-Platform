import asyncio
from types import SimpleNamespace
from notsip.agent import Agent
from notsip.config import settings
from notsip.policy import Policy
from notsip.store import Store
from notsip.tools import Registry,Tool
from notsip.world import WorldModel


def test_android_command_requires_capability_and_creates_approval(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'data_dir',str(tmp_path));monkeypatch.setattr(settings,'autonomy_level',2);monkeypatch.setattr(settings,'capability_levels',{'ANDROID_CONTROL':3})
    registry=Registry();store=Store(tmp_path);registry.add(Tool('android_command','android','ANDROID_CONTROL',2,{'type':'object','properties':{}},lambda **kwargs:{'status':'QUEUED'}))
    agent=Agent(settings,store,Policy(2),registry,SimpleNamespace(enabled=False,fallback_enabled=False),WorldModel(store))
    result=asyncio.run(agent.run_tool('android_command',{'device_id':'d1','action':'send_sms','payload':{'number':'x','text':'y'}}))
    assert result['status']=='PARTIAL_SUCCESS'
    assert result['approval_required'] is True
    assert result['capability']=='ANDROID_CONTROL'
