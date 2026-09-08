from pathlib import Path


def test_approval_execution_requires_central_execution_gate():
    text=Path('src/notsip/approval_hardening.py').read_text(encoding='utf-8')
    assert "_notsip_guarded" in text
    assert "approved tool is not protected by the central execution gate" in text
