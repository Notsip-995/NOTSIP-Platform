from pathlib import Path


def test_pairing_route_rejects_existing_device_owned_by_other_actor():
    text=Path('src/notsip/pairing_hardening.py').read_text(encoding='utf-8')
    assert "device_id is already owned by another actor" in text
    assert "existing_owner=store.device_owner(body.device_id)" in text


def test_device_transport_rejects_revoked_devices_and_foreign_results():
    text=Path('src/notsip/pairing_hardening.py').read_text(encoding='utf-8')
    assert "device is revoked" in text
    assert "command does not belong to authenticated device" in text
    assert "status':'ALREADY_RECORDED'" in text
    assert "X-NOTSIP-Device-ID" in text
    assert "X-NOTSIP-Device-Token" in text
