from pathlib import Path
from notsip.actor_context import set_actor,reset_actor,current_actor
from notsip.agent import Agent
from notsip.conversations import ConversationStore
from notsip.product_layer import ApprovalStore
from notsip.policy import Policy
from notsip.tools import Registry
from notsip.provider import Provider
from notsip.store import Store
from notsip.world import WorldModel
from notsip.config import Settings


def test_conversation_store_isolated_by_actor(tmp_path):
    first=ConversationStore(tmp_path,'issuer:user-a').create('A')
    second=ConversationStore(tmp_path,'issuer:user-b').create('B')
    assert [x['title'] for x in ConversationStore(tmp_path,'issuer:user-a').list()]==['A']
    assert [x['title'] for x in ConversationStore(tmp_path,'issuer:user-b').list()]==['B']
    assert ConversationStore(tmp_path,'issuer:user-a').history(second['id'],20)==[]


def test_agent_uses_current_actor_for_profile_and_memory(tmp_path,monkeypatch):
    settings=Settings(data_dir=str(tmp_path),host='127.0.0.1')
    store=Store(tmp_path);agent=Agent(settings,store,Policy(2),Registry(),Provider('', '', ''),WorldModel(store))
    ta=set_actor('issuer:user-a')
    try:
        assert agent.user=='issuer:user-a'
        agent.profile.update(preferred_name='Alice')
        store.remember(agent.user,'semantic','Alice private fact')
    finally:reset_actor(ta)
    tb=set_actor('issuer:user-b')
    try:
        assert agent.user=='issuer:user-b'
        assert agent.profile.load()['preferred_name']==''
        assert store.memories(agent.user)==[]
    finally:reset_actor(tb)


def test_approval_store_context_cannot_be_cross_executed():
    approvals=ApprovalStore(Path('/tmp'))
    token=set_actor('issuer:user-a')
    try:item=approvals.request('demo','reason',{'tool':'demo','args':{'x':1},'actor':current_actor()},ttl=60);approvals.decide(item['id'],True)
    finally:reset_actor(token)
    token=set_actor('issuer:user-b')
    try:
        from notsip.execution_gate import ToolExecutionGate
        ToolExecutionGate.configure(Policy(4),approvals)
        assert ToolExecutionGate._approved('demo',{'x':1}) is False
    finally:reset_actor(token)
