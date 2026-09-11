from pathlib import Path


def test_active_pairing_layer_uses_actor_binding_and_single_result_transition():
    text=Path('src/notsip/pairing_hardening.py').read_text(encoding='utf-8')
    assert "pairing:owner:" in text
    assert "device_id is already owned by another actor" in text
    assert "status not in _ALLOWED_COMMAND_STATUSES" in text
    assert "store.command_result(command_id,status,result,did)" in text
    assert "command_status!='DELIVERED'" in text
    assert "_placeholder(store)" in text
