import asyncio
from types import SimpleNamespace
from notsip.agent import Agent
from notsip.policy import Policy
from notsip.store import Store
from notsip.tools import Registry
from notsip.world import WorldModel
from notsip.config import settings


def test_oauth_revoke_is_high_risk_and_requires_manage_accounts(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'data_dir',str(tmp_path));monkeypatch.setattr(settings,'autonomy_level',2);monkeypatch.setattr(settings,'capability_levels',{'MANAGE_ACCOUNTS':3})
    agent=Agent(settings,Store(tmp_path),Policy(2),Registry(),SimpleNamespace(enabled=False,fallback_enabled=False),WorldModel(Store(tmp_path)))
    # product_routes adds the tool in the running assembly; the core policy contract itself must deny it below level 3.
    decision=agent.policy.decide(3,True,'MANAGE_ACCOUNTS')
    assert decision.allowed is False
    assert decision.needs_confirmation is True
