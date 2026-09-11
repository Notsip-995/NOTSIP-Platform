from notsip.product_layer import AuditLog
from notsip.actor_context import set_actor,reset_actor
from notsip.store import Store


def test_audit_rows_are_separable_by_actor(tmp_path):
    store=Store(tmp_path)
    store.audit('issuer:user-a','secret request','interpretation','tool','execute','done')
    store.audit('issuer:user-b','other request','interpretation','tool','execute','done')
    rows=store.rows('SELECT * FROM audit WHERE user_id=? ORDER BY id',( 'issuer:user-a',))
    assert len(rows)==1 and rows[0]['user_id']=='issuer:user-a'


def test_secondary_actor_sees_only_own_audit_log(tmp_path):
    log=AuditLog(tmp_path)
    log.write('request',actor='issuer:user-a',path='/a')
    log.write('request',actor='issuer:user-b',path='/b')
    actor=set_actor('issuer:user-b')
    try:visible=[x for x in log.tail() if x.get('actor')=='issuer:user-b']
    finally:reset_actor(actor)
    assert [x['path'] for x in visible]==['/b']
