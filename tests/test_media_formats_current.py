from pathlib import Path


def test_media_preserves_known_input_audio_formats():
    text=Path('src/notsip/media.py').read_text(encoding='utf-8')
    assert "'audio/mpeg':'mp3'" in text
    assert "'audio/mp4':'m4a'" in text
    assert "ext=_extension_for_mime(mime)" in text


def test_media_rejects_unsupported_audio_and_mismatched_tts_bytes():
    text=Path('src/notsip/media.py').read_text(encoding='utf-8')
    assert "unsupported audio MIME type" in text
    assert "unsupported TTS output format" in text
    assert "do not match requested" in text
