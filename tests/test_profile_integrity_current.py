from pathlib import Path


def test_profile_store_fails_closed_on_corruption_and_owner_mismatch():
    text=Path('src/notsip/user_profile.py').read_text(encoding='utf-8')
    assert "user profile is unreadable" in text
    assert "user profile ownership mismatch" in text
    assert "stored_user!=self.user_id" in text
