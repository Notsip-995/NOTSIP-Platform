import asyncio
from types import SimpleNamespace
from fastapi import FastAPI
from notsip.actor_context import reset_actor, set_actor
from notsip.config import settings
from notsip.product_layer import ApprovalStore
from notsip.security import AuthManager
from notsip.session_hardening import attach
from notsip.agent import Agent
from notsip.policy import Policy
from notsip.store import Store
from notsip.tools import Registry
from notsip.world import WorldModel


def test_logout_revokes_session(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'data_dir', str(tmp_path))
    auth = AuthManager(settings, tmp_path)
    token = auth.mint_session({'sub': 'primary-user'})
    assert auth.validate_session(token)
    app = FastAPI()
    store = Store(tmp_path)
    agent = Agent(settings, store, Policy(0), Registry(), SimpleNamespace(enabled=False, fallback_enabled=False), WorldModel(store))
    async def require_auth(_): return None
    attach(app, require_auth, agent, tmp_path, auth=auth)
    route = next(r for r in app.routes if getattr(r, 'path', '') == '/api/logout')
    handle = set_actor('primary-user')
    try:
        request = SimpleNamespace(cookies={'notsip_session': token})
        response = asyncio.run(route.endpoint(request, None))
    finally:
        reset_actor(handle)
    assert response.body == b'{"status":"LOGGED_OUT","actor":"primary-user"}'
    assert not auth.validate_session(token)
