from pathlib import Path
import json
import time
import pytest


def test_android_client_reads_hardened_pairing_token():
    text=Path('android/app/src/main/java/com/notsip/mobile/NotsipClient.kt').read_text(encoding='utf-8')
    assert 'optString("device_token")' in text
    assert 'NOTSIP pairing response did not include a device token' in text


def test_android_result_queue_reconciles_corrupt_records_and_secure_prefs_fail_closed():
    service=Path('android/app/src/main/java/com/notsip/mobile/NotsipCommandService.kt').read_text(encoding='utf-8')
    secure=Path('android/app/src/main/java/com/notsip/mobile/SecurePrefs.kt').read_text(encoding='utf-8')
    assert 'catch(_:JSONException)' in service
    assert 'Android pending command result was locally corrupted' in service
    assert 'catch(_:Exception){return}' in service
    assert 'throw SecurityException("Corrupted secure preference: $name")' in secure
    assert 'throw SecurityException("Unable to decrypt secure preference: $name", e)' in secure


def test_command_result_is_single_transition(tmp_path):
    from notsip.store import Store
    store=Store(tmp_path)
    store.pair_device('d1','Device','android','', 'token')
    command_id=store.queue_command('d1','send_sms',{'text':'x'})
    pulled=store.pull_commands('d1')
    assert pulled and pulled[0]['id']==command_id
    assert store.command_result(command_id,'SUCCESS',{'verified':True},'d1') is True
    assert store.command_result(command_id,'SUCCESS',{'verified':True,'replay':True},'d1') is False
    row=store.row('SELECT status,result FROM commands WHERE id=?',(command_id,))
    assert row['status']=='SUCCESS'
    assert json.loads(row['result'])['verified'] is True
