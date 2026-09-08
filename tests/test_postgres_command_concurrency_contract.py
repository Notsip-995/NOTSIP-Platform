from pathlib import Path


def test_postgres_command_claim_uses_skip_locked():
    source=Path('src/notsip/postgres_store.py').read_text(encoding='utf-8')
    assert 'FOR UPDATE SKIP LOCKED' in source
    assert "status='PENDING'" in source


def test_command_results_require_device_binding():
    sqlite=Path('src/notsip/store.py').read_text(encoding='utf-8')
    postgres=Path('src/notsip/postgres_store.py').read_text(encoding='utf-8')
    assert "if not device_id:return False" in sqlite
    assert 'if device_id is None:return False' in postgres
