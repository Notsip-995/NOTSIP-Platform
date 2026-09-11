import json
import time
from pathlib import Path


def test_stale_delivered_command_becomes_unknown_not_pending(tmp_path):
    from notsip.store import Store
    from notsip.actor_context import set_actor, reset_actor
    store = Store(tmp_path)
    token = set_actor('actor-a')
    try:
        store.pair_device('device-a', 'A', 'android', '', 'device-token')
        command_id = store.queue_command('device-a', 'notify', {'text':'x'})
        store.pull_commands('device-a')
    finally:
        reset_actor(token)
    stale = time.time() - 1000
    store.exec('UPDATE commands SET updated=? WHERE id=?', (stale, command_id))
    store.exec("UPDATE devices SET last_seen=?, status='STALE' WHERE id=?", (stale, 'device-a'))
    rows = store.reconcile_commands(300)
    assert [r['id'] for r in rows] == [command_id]
    command = store.row('SELECT status,result FROM commands WHERE id=?', (command_id,))
    assert command['status'] == 'UNKNOWN'
    assert json.loads(command['result'])['verified'] is False


def test_reconciliation_source_handles_orphaned_commands_for_both_backends():
    sqlite=Path('src/notsip/store.py').read_text(encoding='utf-8')
    postgres=Path('src/notsip/postgres_store.py').read_text(encoding='utf-8')
    for text in (sqlite,postgres):
        assert 'LEFT JOIN devices' in text
        assert 'd.id IS NULL' in text
        assert "status='UNKNOWN'" in text
        assert 'device was removed, revoked' in text
