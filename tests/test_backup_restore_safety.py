from pathlib import Path
import zipfile
from notsip.product_layer import BackupManager
from notsip.backup_hardening import install


def test_restore_rolls_back_on_replacement_failure(tmp_path,monkeypatch):
    manager=BackupManager(tmp_path);install(manager)
    (tmp_path/'a.txt').write_text('OLD-A')
    (tmp_path/'b.txt').write_text('OLD-B')
    archive=manager.dir/'restore.zip'
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('a.txt','NEW-A');z.writestr('b.txt','NEW-B')
    original_move=__import__('shutil').move
    calls={'n':0}
    def failing_move(src,dst):
        calls['n']+=1
        if calls['n']==4:raise OSError('injected replacement failure')
        return original_move(src,dst)
    monkeypatch.setattr(__import__('shutil'),'move',failing_move)
    try:manager.restore('restore.zip',True)
    except OSError:pass
    else:raise AssertionError('restore unexpectedly succeeded')
    assert (tmp_path/'a.txt').read_text()=='OLD-A'
    assert (tmp_path/'b.txt').read_text()=='OLD-B'
