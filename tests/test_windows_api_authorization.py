import asyncio
from types import SimpleNamespace
from notsip.agent import Agent
from notsip.config import settings
from notsip.policy import Policy
from notsip.store import Store
from notsip.tools import Registry,Tool
from notsip.world import WorldModel


def test_windows_mutation_tools_require_capability(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'data_dir',str(tmp_path));monkeypatch.setattr(settings,'autonomy_level',2);monkeypatch.setattr(settings,'capability_levels',{'CONTROL_COMPUTER':3})
    registry=Registry();store=Store(tmp_path)
    registry.add(Tool('windows_click','click','CONTROL_COMPUTER',1,{'type':'object','properties':{}},lambda:{'status':'SUCCESS'}))
    agent=Agent(settings,store,Policy(2),registry,SimpleNamespace(enabled=False,fallback_enabled=False),WorldModel(store))
    result=asyncio.run(agent.run_tool('windows_click',{}))
    assert result['status']=='PARTIAL_SUCCESS'
    assert result['capability']=='CONTROL_COMPUTER'
    assert result['required_level']==3
