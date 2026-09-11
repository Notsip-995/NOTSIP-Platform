import asyncio
import json
from types import SimpleNamespace

from fastapi import FastAPI

from notsip.agent import Agent
from notsip.approval_hardening import attach as attach_approval
from notsip.config import SECRET_FIELDS, settings
from notsip.policy import Policy, Risk
from notsip.product_layer import ApprovalStore, ConfigStore
from notsip.security import SecretStore
from notsip.store import Store
from notsip.tools import Registry, Tool
from notsip.world import WorldModel


def test_database_url_is_persistent_configuration(tmp_path):
    config = ConfigStore(tmp_path)
    config.save({'database_url': 'postgresql://user:password@example/db', 'node_name': 'TEST'})
    assert config.load()['settings']['database_url'] == 'postgresql://user:password@example/db'
    assert 'database_url' not in SECRET_FIELDS


def test_scheduler_claim_is_atomic(tmp_path):
    store = Store(tmp_path)
    tid = store.task('demo', 'PENDING', 0, 'agent', {'x': 1}, 0, None)
    first = store.claim_task(tid, json.dumps({'worker_id': 'a'}))
    second = store.claim_task(tid, json.dumps({'worker_id': 'b'}))
    assert first is True
    assert second is False
    assert store.row('SELECT state FROM tasks WHERE id=?', (tid,))['state'] == 'RUNNING'


def test_command_result_is_device_bound(tmp_path):
    store = Store(tmp_path)
    store.pair_device('a', 'A', 'android', '', 'token-a')
    store.pair_device('b', 'B', 'android', '', 'token-b')
    command_id = store.queue_command('a', 'ping', {})
    assert store.command_result(command_id, 'SUCCESS', {'ok': True}, 'b') is False
    assert store.command_result(command_id, 'SUCCESS', {'ok': True}, 'a') is True


def test_approval_execution_is_one_time(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'data_dir', str(tmp_path))
    monkeypatch.setattr(settings, 'autonomy_level', 4)
    monkeypatch.setattr(settings, 'capability_levels', {'COMPUTE': 0})
    store = Store(tmp_path)
    registry = Registry()
    calls = {'n': 0}

    def calculate():
        calls['n'] += 1
        return {'status': 'SUCCESS', 'value': 42}

    registry.add(Tool('calculator', 'test', 'COMPUTE', Risk.LOW, {'type': 'object', 'properties': {}}, calculate))
    agent = Agent(settings, store, Policy(4), registry, SimpleNamespace(enabled=False, fallback_enabled=False), WorldModel(store))
    item = agent.approvals.request('calculator', 'test', {'tool': 'calculator', 'args': {}, 'actor': 'primary-user'})

    app = FastAPI()

    class Log:
        def write(self, *args, **kwargs):
            return None

    async def require_auth(request):
        return None

    attach_approval(app, require_auth=require_auth, approvals=agent.approvals, registry=registry, audit_log=Log(), agent=agent)
    route = next(r for r in app.routes if getattr(r, 'path', None) == '/api/approvals/{approval_id}')
    first = asyncio.run(route.endpoint(item['id'], {'approved': True, 'execute': True}, None))
    assert first['status'] == 'EXECUTED'
    assert calls['n'] == 1
    try:
        asyncio.run(route.endpoint(item['id'], {'approved': True, 'execute': True}, None))
    except Exception as exc:
        assert getattr(exc, 'status_code', None) == 409
    else:
        raise AssertionError('second approval execution must fail')


def test_database_url_is_not_secret():
    assert 'database_url' not in SECRET_FIELDS


def test_canonical_route_set_has_no_duplicates():
    from notsip.core_runtime import app
    seen = set()
    duplicates = []
    for route in app.routes:
        methods = tuple(sorted(getattr(route, 'methods', set())))
        if not methods:
            continue
        key = (getattr(route, 'path', ''), methods)
        if key in seen:
            duplicates.append(key)
        seen.add(key)
    assert not duplicates, duplicates
