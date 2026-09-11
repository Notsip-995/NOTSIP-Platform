from pathlib import Path


def test_product_layer_maintenance_keeps_self_apply_contract():
    source=Path('src/notsip/product_layer.py').read_text(encoding='utf-8')
    assert 'class Maintenance:' in source
    assert 'def apply_patch(self,patch_text,confirmation):' in source
    assert 'SelfMaintenance(self.root).apply_patch' in source


def test_product_layer_exposes_capability_probe_contract():
    source=Path('src/notsip/product_layer.py').read_text(encoding='utf-8')
    assert 'class CapabilityProbe:' in source
    assert 'def snapshot(self):' in source
