import json
from pathlib import Path
import pytest

from notsip.product_layer import AuditLog, ConfigStore


def test_audit_append_refuses_tampered_history(tmp_path):
    log = AuditLog(tmp_path)
    log.write('first', actor='primary-user')
    path = Path(tmp_path) / 'runtime' / 'audit.jsonl'
    rows = [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]
    rows[0]['event'] = 'tampered'
    path.write_text('\n'.join(json.dumps(x, sort_keys=True, separators=(',', ':')) for x in rows) + '\n', encoding='utf-8')
    with pytest.raises(RuntimeError, match='audit hash chain verification failed'):
        log.write('second', actor='primary-user')


def test_database_url_can_be_cleared_from_secret_store(tmp_path):
    config = ConfigStore(tmp_path)
    config.save({'database_url': 'postgresql://u:p@example.test/db'})
    assert config.load()['settings']['database_url'].startswith('postgresql://')
    config.save({'database_url': ''})
    assert config._secret_store().get('NOTSIP_DATABASE_URL') is None


def test_plaintext_legacy_database_url_is_migrated(tmp_path):
    config = ConfigStore(tmp_path)
    config.path.write_text(json.dumps({'version': 1, 'settings': {'database_url': 'postgresql://legacy:pw@example.test/db'}}), encoding='utf-8')
    loaded = config.load()
    assert loaded['settings']['database_url'].startswith('postgresql://')
    persisted = json.loads(config.path.read_text(encoding='utf-8'))
    assert 'database_url' not in persisted['settings']
    assert config._secret_store().get('NOTSIP_DATABASE_URL') == 'postgresql://legacy:pw@example.test/db'
