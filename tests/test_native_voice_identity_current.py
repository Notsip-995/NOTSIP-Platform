from pathlib import Path


def test_native_voice_emits_audio_evidence_and_bridge_verifies_scoped_path():
    native=Path('src/notsip/native_voice.py').read_text(encoding='utf-8')
    bridge=Path('src/notsip/voice_bridge.py').read_text(encoding='utf-8')
    assert "'audio_path':evidence" in native
    assert "'audio_mime':'audio/wav'" in native
    assert "candidate=(Path(media_root)/audio_path).resolve()" in bridge
    assert "voice evidence path escaped media directory" in bridge
    assert "speaker_identity.verify(audio" in bridge
