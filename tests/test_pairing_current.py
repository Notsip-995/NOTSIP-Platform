from pathlib import Path


def test_pairing_route_rejects_existing_device_owned_by_other_actor():
    text=Path('src/notsip/pairing_hardening.py').read_text(encoding='utf-8')
    assert "device_id is already owned by another actor" in text
    assert "existing_owner=store.device_owner(body.device_id)" in text
