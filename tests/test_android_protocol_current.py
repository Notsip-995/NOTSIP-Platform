from pathlib import Path


def test_android_client_reads_hardened_pairing_token():
    text=Path('android/app/src/main/java/com/notsip/mobile/NotsipClient.kt').read_text(encoding='utf-8')
    assert 'optString("device_token")' in text
    assert 'NOTSIP pairing response did not include a device token' in text
