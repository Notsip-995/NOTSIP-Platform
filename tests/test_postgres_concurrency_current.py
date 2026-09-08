from pathlib import Path


def test_postgres_command_claim_uses_row_locking_and_skip_locked():
    text=Path('src/notsip/database_concurrency_hardening.py').read_text(encoding='utf-8')
    assert 'FOR UPDATE SKIP LOCKED' in text
    assert "status='PENDING'" in text
    assert "backend.pull_commands=pull_commands" in text
