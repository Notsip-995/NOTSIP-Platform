import hashlib,hmac
from notsip.nodes import NodeRegistry
from notsip.store import Store
from notsip.world import WorldModel


def test_registered_node_is_projected_into_world_model(tmp_path):
    store=Store(tmp_path);world=WorldModel(store);nodes=NodeRegistry(store,'shared',lease_seconds=90);nodes.world=world
    nonce='unique-nonce';sig=hmac.new(b'shared',b'node-1:'+nonce.encode(),hashlib.sha256).hexdigest()
    result=nodes.register('node-1','Compute Node','linux',['COMPUTE'],'',nonce,sig)
    assert result['node_id']=='node-1'
    entities=world.snapshot()['entities']
    assert any(e['id']=='node:node-1' and e['kind']=='device' for e in entities)


def test_revoked_node_is_reflected_in_world_model(tmp_path):
    store=Store(tmp_path);world=WorldModel(store);nodes=NodeRegistry(store,'shared');nodes.world=world
    store.pair_device('node-2','Robot','linux','','token')
    nodes.revoke('node-2')
    item=next(e for e in world.snapshot()['entities'] if e['id']=='node:node-2')
    assert item['data']['status']=='REVOKED'
