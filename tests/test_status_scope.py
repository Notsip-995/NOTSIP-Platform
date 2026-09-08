import json
from notsip.status_scope_hardening import _own_task,_own_fact


def test_task_scope_rejects_foreign_actor():
    task={'data':json.dumps({'actor':'issuer:user-a'})}
    assert _own_task(task,'issuer:user-a') is True
    assert _own_task(task,'issuer:user-b') is False


def test_public_fact_and_private_fact_scope(tmp_path):
    class DeviceStore:
        def device_owned_by(self,device_id,actor):return device_id=='device-a' and actor=='issuer:user-a'
    store=DeviceStore()
    assert _own_fact({'source':'brave','metadata':'{}'},'issuer:user-b',store) is True
    assert _own_fact({'source':'private','metadata':json.dumps({'actor':'issuer:user-a'})},'issuer:user-b',store) is False
    assert _own_fact({'source':'private','metadata':json.dumps({'device_id':'device-a'})},'issuer:user-a',store) is True
