from notsip.store import Store
from notsip.actor_context import set_actor,reset_actor


def test_device_pairing_and_command_queue_are_actor_scoped(tmp_path):
    store=Store(tmp_path)
    ta=set_actor('actor:a')
    try:
        store.pair_device('phone-a','A','android','', 'token-a')
        assert store.device_owned_by('phone-a') is True
        assert store.queue_command('phone-a','notify',{'text':'ok'})
    finally:reset_actor(ta)
    tb=set_actor('actor:b')
    try:
        assert store.devices()==[]
        assert store.device_owned_by('phone-a') is False
        try:store.queue_command('phone-a','notify',{'text':'should fail'})
        except PermissionError:pass
        else:raise AssertionError('cross-actor device command was accepted')
    finally:reset_actor(tb)


def test_legacy_unowned_device_defaults_to_primary_owner(tmp_path):
    store=Store(tmp_path)
    store.exec("INSERT INTO devices(id,name,platform,public_key,token_hash,last_seen,status,data) VALUES(?,?,?,?,?,?,?,?)",('legacy','Legacy','android','','hash',0,'ONLINE','{}'))
    ta=set_actor('actor:b')
    try:assert store.device_owned_by('legacy') is False
    finally:reset_actor(ta)
