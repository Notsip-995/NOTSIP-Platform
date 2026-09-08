from pathlib import Path


def test_tagged_android_release_cannot_fall_back_to_debug():
    text=Path('.github/workflows/release.yml').read_text(encoding='utf-8')
    assert 'Require signing material for tagged release' in text
    assert 'Tagged Android releases require complete keystore/signing secrets.' in text
    assert 'Publish debug Android asset' not in text


def test_tagged_windows_release_verifies_authenticode_publisher():
    text=Path('.github/workflows/release.yml').read_text(encoding='utf-8')
    assert 'Get-AuthenticodeSignature' in text
    assert '$sig.Status -ne \'Valid\'' in text
    assert 'WINDOWS_PUBLISHER_THUMBPRINT' in text
    assert 'Authenticode publisher mismatch' in text
