import json
from pathlib import Path
import pytest

from notsip.product_layer import ConfigStore, ProcessGuard


def test_database_url_round_trips_securely(tmp_path):
    store = ConfigStore(tmp_path)
    url = 'postgresql://user:password@example.test/not-sip'
    store.save({'database_url': url, 'node_name': 'NOTSIP'})
    persisted = json.loads(store.path.read_text(encoding='utf-8'))
    assert 'database_url' not in persisted['settings']
    assert store.load()['settings']['database_url'] == url


def test_corrupt_instance_lock_fails_closed(tmp_path):
    lock = Path(tmp_path) / 'runtime' / 'instance.lock'
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text('{not-json', encoding='utf-8')
    with pytest.raises(RuntimeError, match='instance lock is corrupt'):
        ProcessGuard(root=tmp_path).acquire()


def test_incomplete_instance_lock_fails_closed(tmp_path):
    lock = Path(tmp_path) / 'runtime' / 'instance.lock'
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps({'pid': 0, 'created': 0}), encoding='utf-8')
    with pytest.raises(RuntimeError, match='missing required ownership metadata'):
        ProcessGuard(root=tmp_path).acquire()
