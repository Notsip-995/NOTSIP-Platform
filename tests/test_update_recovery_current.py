from pathlib import Path


def test_update_recovery_requires_signed_rollback_and_runs_before_app_import():
    recovery = Path('src/notsip/update_recovery.py').read_text(encoding='utf-8')
    main = Path('src/notsip/__main__.py').read_text(encoding='utf-8')
    assert "previous-*.exe" in recovery
    assert "reconcile_frozen_update" in main
    assert "RECOVERY_UNAVAILABLE" in main
    assert "_authenticode_valid" in recovery
