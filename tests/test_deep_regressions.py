import asyncio
import json

from fastapi import FastAPI

from notsip.approval_hardening import attach as attach_approval
from notsip.config import SECRET_FIELDS
from notsip.product_layer import ApprovalStore, ConfigStore
from notsip.security import SecretStore
from notsip.store import Store


def test_database_url_is_persistent_configuration(tmp_path):
    config = ConfigStore(tmp_path)
    config.save({'database_url': 'postgresql://user:password@example/db', 'node_name': 'TEST'})
    assert 'database_url' not in config.load()['settings']
    secrets = SecretStore(tmp_path)
    secrets.set('NOTSIP_DATABASE_URL', 'postgresql://user:password@example/db')
    assert secrets.get('NOTSIP_DATABASE_URL') == 'postgresql://user:password@example/db'


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


def test_approval_execution_is_one_time(tmp_path):
    approvals = ApprovalStore(tmp_path)
    item = approvals.request('calculator', 'test', {'tool': 'calculator', 'args': {}})
    calls = {'n': 0}

    class Tool:
        def fn(self, **kwargs):
            calls['n'] += 1
            return {'status': 'SUCCESS'}

    class Registry:
        def get(self, name):
            return Tool() if name == 'calculator' else None

    app = FastAPI()
    class Log:
        def write(self, *args, **kwargs):
            return None
    async def require_auth(request):
        return None
    attach_approval(app, require_auth=require_auth, approvals=approvals, registry=Registry(), audit_log=Log())
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


def test_database_url_is_secret():
    assert 'database_url' in SECRET_FIELDS


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
