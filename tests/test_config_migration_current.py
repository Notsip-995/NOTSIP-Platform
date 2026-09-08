from pathlib import Path


def test_setup_migration_covers_all_runtime_secret_fields():
    text=Path('src/notsip/setup_hardening.py').read_text(encoding='utf-8')
    assert 'speaker_identity_token' in text
    assert "if not mod.auth.secrets.get(secret_name):mod.auth.secrets.set(secret_name,str(value))" in text
    assert "raw.pop(key,None);changed=True" in text


def test_setup_migration_rewrites_config_without_legacy_secrets():
    text=Path('src/notsip/setup_hardening.py').read_text(encoding='utf-8')
    assert '_migrate_legacy_config(mod)' in text
    assert 'mod.config_store.save(raw)' in text
