from pathlib import Path


def test_android_result_route_validates_status_and_payload_size():
    text=Path('src/notsip/product_routes.py').read_text(encoding='utf-8')
    assert "_ALLOWED_COMMAND_STATUSES={'SUCCESS','FAILURE','PARTIAL_SUCCESS','UNKNOWN'}" in text
    assert 'invalid command result status' in text
    assert 'command result exceeds maximum size' in text
    assert "MAX_COMMAND_RESULT_BYTES=1024*1024" in text
