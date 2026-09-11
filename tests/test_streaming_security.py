from pathlib import Path


def test_streaming_stt_endpoint_requires_ws_and_safe_host():
    text=Path('src/notsip/streaming.py').read_text(encoding='utf-8')
    assert "parsed.scheme not in {'wss','ws'}" in text
    assert "ws streaming endpoints are restricted to loopback addresses" in text
    assert "streaming STT endpoint resolved to a non-public address" in text
    assert "proxy=None" in text
    assert "invalid control JSON" in text
    assert "invalid perception payload" in text
