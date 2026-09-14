import json
from pathlib import Path

from notsip.product_layer import AuditLog


def test_startup_recovery_quarantines_corrupt_json(tmp_path):
    log = AuditLog(tmp_path)
    log.path.parent.mkdir(parents=True, exist_ok=True)
    log.path.write_text('{not-json\n', encoding='utf-8')
    result = log.recover()
    assert result['recovered'] is True
    assert result['quarantined']
    assert (tmp_path / 'runtime' / 'quarantine').exists()
    chain = log.verify()
    assert chain['valid'] is True
    assert chain['entries'] == 1  # the audit.chain.reset marker


def test_startup_recovery_resets_tampered_chain(tmp_path):
    log = AuditLog(tmp_path)
    log.write('first')
    path = Path(tmp_path) / 'runtime' / 'audit.jsonl'
    rows = [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]
    rows[0]['event'] = 'tampered'
    path.write_text('\n'.join(json.dumps(x, sort_keys=True, separators=(',', ':')) for x in rows) + '\n', encoding='utf-8')
    result = log.recover()
    assert result['recovered'] is True
    assert (tmp_path / 'runtime' / 'quarantine').exists()
    log.write('second')
    assert log.verify()['valid'] is True


def test_startup_recovery_is_noop_on_valid_log(tmp_path):
    log = AuditLog(tmp_path)
    log.write('one')
    log.write('two')
    result = log.recover()
    assert result['recovered'] is False
    assert result['quarantined'] is None
    assert result['entries'] == 2
    assert log.verify()['valid'] is True