from pathlib import Path


def test_secure_backup_excludes_master_key():
    text=Path('src/notsip/backup_hardening.py').read_text(encoding='utf-8')
    assert "if rel.as_posix()=='master.key':continue" in text
    assert "security_note" in text
    assert "manager.create=create_safe" in text
