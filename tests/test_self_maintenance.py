from notsip.self_maintenance import SelfMaintenance


def test_inventory_and_read(tmp_path):
    (tmp_path/'src').mkdir()
    (tmp_path/'src'/'demo.py').write_text('x=1\n', encoding='utf-8')
    sm=SelfMaintenance(tmp_path)
    paths={x['path'] for x in sm.inventory()}
    assert 'src/demo.py' in paths
    assert sm.read('src/demo.py')=='x=1\n'


def test_self_modify_requires_explicit_enable_and_confirmation(tmp_path, monkeypatch):
    sm=SelfMaintenance(tmp_path)
    monkeypatch.setenv('NOTSIP_SELF_MODIFY_ENABLED','false')
    try:
        sm.apply_patch('', 'APPLY_SELF_CHANGE')
    except PermissionError:
        pass
    else:
        raise AssertionError('self modification should be disabled')
