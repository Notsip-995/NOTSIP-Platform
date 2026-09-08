from notsip.nodes import NodeRegistry
from notsip.store import Store


def test_federation_nonce_replay_is_rejected(tmp_path):
    store=Store(tmp_path)
    nodes=NodeRegistry(store,'shared-secret')
    nonce='fresh-1'
    signature=nodes.sign('node-1',nonce)
    first=nodes.register('node-1','Node','test',[],nonce=nonce,signature=signature)
    assert first['token']
    try:
        nodes.register('node-1','Node','test',[],nonce=nonce,signature=signature)
    except PermissionError as exc:
        assert 'replayed' in str(exc)
    else:
        raise AssertionError('replayed federation nonce must be rejected')


def test_federation_heartbeat_nonce_replay_is_rejected(tmp_path):
    store=Store(tmp_path)
    nodes=NodeRegistry(store,'shared-secret')
    reg_nonce='reg-1'; reg_sig=nodes.sign('node-1',reg_nonce)
    token=nodes.register('node-1','Node','test',[],nonce=reg_nonce,signature=reg_sig)['token']
    nonce='beat-1'; signature=nodes.sign('node-1',nonce)
    nodes.heartbeat('node-1',token,[],{},nonce,signature)
    try:
        nodes.heartbeat('node-1',token,[],{},nonce,signature)
    except PermissionError as exc:
        assert 'replayed' in str(exc)
    else:
        raise AssertionError('replayed heartbeat nonce must be rejected')
