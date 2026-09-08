import asyncio
from pathlib import Path
from notsip.actor_context import set_actor,reset_actor
from notsip.agent import Agent
from notsip.policy import Policy
from notsip.product_layer import ApprovalStore
from notsip.store import Store
from notsip.tools import Registry,Tool
from notsip.provider import Provider
from notsip.world import WorldModel
from notsip.config import Settings


def test_unverified_voice_cannot_execute_high_risk_tool(tmp_path):
    settings=Settings(data_dir=str(tmp_path),host='127.0.0.1',autonomy_level=4)
    store=Store(tmp_path);registry=Registry();called=[]
    registry.add(Tool('danger','Danger','CONTROL_COMPUTER',2,{},lambda:called.append(True),True))
    agent=Agent(settings,store,Policy(4),registry,Provider('', '', ''),WorldModel(store))
    token=set_actor('voice:unverified')
    try:result=asyncio.run(agent.run_tool('danger',{}))
    finally:reset_actor(token)
    assert result['status']=='FAILURE' and 'verified speaker' in result['error'] and called==[]


def test_verified_primary_voice_can_follow_normal_policy(tmp_path):
    settings=Settings(data_dir=str(tmp_path),host='127.0.0.1',autonomy_level=4)
    store=Store(tmp_path);registry=Registry();called=[]
    registry.add(Tool('safe','Safe','COMPUTE',0,{},lambda:{'status':'SUCCESS','called':True}))
    agent=Agent(settings,store,Policy(4),registry,Provider('', '', ''),WorldModel(store))
    token=set_actor('primary-user')
    try:result=asyncio.run(agent.run_tool('safe',{}))
    finally:reset_actor(token)
    assert result['status']=='SUCCESS'
