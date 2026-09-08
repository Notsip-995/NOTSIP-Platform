from pathlib import Path


def test_uia_control_tree_surfaces_traversal_errors():
    text=Path('src/notsip/windows_automation.py').read_text(encoding='utf-8')
    assert "errors=[]" in text
    assert "status='SUCCESS' if not errors else 'PARTIAL_SUCCESS'" in text
    assert "'errors':errors[:200]" in text
    assert "'verified':not errors" in text
