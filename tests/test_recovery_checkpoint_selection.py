import json
from pathlib import Path


def test_recovery_uses_newest_verified_checkpoint(tmp_path):
    from notsip.nodes import RecoveryManager
    manager=RecoveryManager(tmp_path)
    older=tmp_path/'recovery'/'checkpoint-1-aa.json'; older.write_text(json.dumps({'marker':'valid','tasks':[]}),encoding='utf-8')
    (tmp_path/'recovery'/'checkpoint-1-aa.sha256').write_text(__import__('hashlib').sha256(older.read_text(encoding='utf-8').encode()).hexdigest()+'  '+older.name+'\n',encoding='utf-8')
    newer=tmp_path/'recovery'/'checkpoint-2-bb.json'; newer.write_text('{corrupt',encoding='utf-8')
    p,state,invalid=manager.latest_verified()
    assert p==older
    assert state['marker']=='valid'
    assert invalid and invalid[0]['path']==newer.relative_to(tmp_path/'recovery').as_posix()
