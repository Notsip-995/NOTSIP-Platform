from pathlib import Path


def test_updater_rollback_failure_is_not_silently_swallowed():
    text=Path('src/notsip/updater.py').read_text(encoding='utf-8')
    assert 'Rollback failed after update failure' in text
    assert 'exit 3' in text
    assert 'Copy-Item -Force {backup_s} {cur_s}; Start-Process {cur_s}' in text
