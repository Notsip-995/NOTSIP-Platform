import asyncio
import json
from pathlib import Path

from notsip.account_store import AccountStore
from notsip.approval_hardening import attach as attach_approval
from notsip.config import Settings
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


def test_approval_is_one_time(tmp_path):
    approvals = ApprovalStore(tmp_path)
    item = approvals.request('calculator', 'test', {'tool': 'calculator', 'args': {'expr': '1+1'}})
    assert approvals.decide(item['id'], True)['status'] == 'APPROVED'
    assert approvals.decide(item['id'], True)['status'] == 'APPROVED'


def test_database_url_not_marked_secret():
    assert 'database_url' not in __import__('notsip.config', fromlist=['SECRET_FIELDS']).SECRET_FIELDS
