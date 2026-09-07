import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from notsip.approval_hardening import attach as attach_approval
from notsip.config import SECRET_FIELDS
from notsip.product_layer import ApprovalStore, ConfigStore
from notsip.store import Store


def test_database_url_is_persistent_configuration(tmp_path):
    store = ConfigStore(tmp_path)
    store.save({'database_url': 'postgresql://example/db', 'node_name': 'TEST'})
    data = store.load()
    assert data['settings']['database_url'] == 'postgresql://example/db'
    assert data['settings']['node_name'] == 'TEST'


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
    with TestClient(app) as client:
        first = client.post(f'/api/approvals/{item["id"]}', json={'approved': True, 'execute': True})
        second = client.post(f'/api/approvals/{item["id"]}', json={'approved': True, 'execute': True})
    assert first.status_code == 200
    assert second.status_code == 409
    assert calls['n'] == 1


def test_database_url_not_marked_secret():
    assert 'database_url' not in SECRET_FIELDS
