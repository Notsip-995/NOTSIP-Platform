from pathlib import Path


def test_windows_master_key_path_does_not_fallback_to_plaintext_storage():
    text=Path('src/notsip/security.py').read_text(encoding='utf-8')
    assert 'refusing to store a plaintext master key' in text
    assert 'self._persist_local_key(p,raw);return raw' in text
    assert 'refusing insecure key fallback' in text
    assert 'self._dpapi(key) or key' not in text
