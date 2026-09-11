from pathlib import Path


def test_setup_ui_exposes_runtime_user_configuration_fields():
    text=Path('setup.html').read_text(encoding='utf-8')
    for field in ('speaker_identity_url','speaker_identity_token','tts_format','voice_sample_rate','flight_planning_url','business_admin_url'):
        assert f'id="{field}"' in text
    assert "const secretKeys" in text
    assert "Configured — leave blank to keep existing secret" in text
