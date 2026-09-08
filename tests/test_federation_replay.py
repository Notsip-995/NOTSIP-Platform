from notsip.nodes import NodeRegistry,RecoveryManager
from notsip.resource_router import ResourceRouter
from notsip.store import Store
import json,time


def test_federation_nonce_replay_is_rejected(tmp_path):
    store=Store(tmp_path)
    nodes=NodeRegistry(store,'shared-secret')
    nonce='fresh-1';signature=nodes.sign('node-1',nonce)
    first=nodes.register('node-1','Node','test',[],nonce=nonce,signature=signature)
    assert first['token']
    try:nodes.register('node-1','Node','test',[],nonce=nonce,signature=signature)
    except PermissionError as exc:assert 'replayed' in str(exc)
    else:raise AssertionError('replayed federation nonce must be rejected')


def test_federation_heartbeat_nonce_replay_is_rejected(tmp_path):
    store=Store(tmp_path);nodes=NodeRegistry(store,'shared-secret')
    reg_nonce='reg-1';reg_sig=nodes.sign('node-1',reg_nonce);token=nodes.register('node-1','Node','test',[],nonce=reg_nonce,signature=reg_sig)['token']
    nonce='beat-1';signature=nodes.sign('node-1',nonce);nodes.heartbeat('node-1',token,[],{},nonce,signature)
    try:nodes.heartbeat('node-1',token,[],{},nonce,signature)
    except PermissionError as exc:assert 'replayed' in str(exc)
    else:raise AssertionError('replayed heartbeat nonce must be rejected')


def test_recovery_checkpoint_detects_tampering(tmp_path):
    recovery=RecoveryManager(tmp_path);path=recovery.checkpoint({'tasks':[],'devices':[],'commands':[],'world':{},'timestamp':time.time()});checkpoint=tmp_path/path
    checkpoint.write_text(checkpoint.read_text(encoding='utf-8').replace('"tasks": []','"tasks": [{"id":"tampered"}]'),encoding='utf-8')
    result=recovery.verify_latest();assert result['valid'] is False;assert 'integrity verification failed' in result['reason']
    try:recovery.restore_state()
    except RuntimeError as exc:assert 'integrity' in str(exc)
    else:raise AssertionError('tampered checkpoint must not restore')


def test_resource_router_does_not_select_expired_leased_node(tmp_path):
    store=Store(tmp_path);store.pair_device('node-1','Node','linux','', 'token')
    store.exec('UPDATE devices SET data=?,status=? WHERE id=?',(json.dumps({'capabilities':['COMPUTE'],'lease_expires':time.time()-1}), 'ONLINE','node-1'))
    router=ResourceRouter(store);result=router.select('COMPUTE');assert result['status']=='BLOCKED_BY_EXTERNAL_ENVIRONMENT'
