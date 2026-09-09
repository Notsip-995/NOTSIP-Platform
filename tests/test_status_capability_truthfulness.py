from types import SimpleNamespace
from notsip.actor_context import reset_actor, set_actor
from notsip.status_scope_hardening import attach
from notsip.config import settings
from notsip.policy import Policy
from notsip.product_layer import ApprovalStore
from notsip.store import Store
from notsip.tools import Registry
from notsip.world import WorldModel
from notsip.agent import Agent
from fastapi import FastAPI


def test_status_does_not_equate_paired_android_with_distributed_node(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'data_dir', str(tmp_path))
    store = Store(tmp_path)
    store.pair_device('android-1', 'Phone', 'android', '', 'token')
    registry = Registry()
    agent = Agent(settings, store, Policy(0), registry, SimpleNamespace(enabled=False, fallback_enabled=False), WorldModel(store))
    app = FastAPI()
    async def auth(_): return None
    web = SimpleNamespace(enabled=False)
    email = SimpleNamespace(enabled=False)
    oidc = SimpleNamespace(configured=False)
    attach(app, auth, store, agent.policy, agent, settings, registry, web, email, SimpleNamespace(oidc=oidc))
    route = next(r for r in app.routes if getattr(r, 'path', '') == '/api/status')
    token = set_actor('primary-user')
    try:
        payload = __import__('asyncio').run(route.endpoint(None))
    finally:
        reset_actor(token)
    assert payload['capabilities']['android_pairing'] is True
    assert payload['capabilities']['distributed_nodes'] is False
