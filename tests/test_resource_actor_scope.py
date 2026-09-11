import pytest
from notsip.actor_context import set_actor, reset_actor
from notsip.resource_router import ResourceRouter, RobotGateway


class Store:
    def __init__(self):
        self.device_rows=[
            {'id':'a-device','name':'A','platform':'windows','status':'ONLINE','last_seen':1.0,'data':'{"owner":"actor-a","capabilities":["camera"]}'},
            {'id':'b-device','name':'B','platform':'linux','status':'ONLINE','last_seen':1.0,'data':'{"owner":"actor-b","capabilities":["camera","control"]}'},
        ]
    def devices(self,owner=None):
        return [r for r in self.device_rows if owner is None or __import__('json').loads(r['data'])['owner']==owner]
    def device_owned_by(self,node_id,owner=None):
        row=next((r for r in self.device_rows if r['id']==node_id),None)
        return bool(row and __import__('json').loads(row['data'])['owner']==owner)
    def row(self,*args): return next((r for r in self.device_rows if r['id']==args[1][0]),None)
    def exec(self,*args): return None
    def queue_command(self,*args): return 'cmd-1'


def test_router_only_selects_current_actor_devices():
    store=Store();router=ResourceRouter(store);token=set_actor('actor-a')
    try: result=router.select('control')
    finally: reset_actor(token)
    assert result['status']=='BLOCKED_BY_EXTERNAL_ENVIRONMENT'


def test_robot_gateway_rejects_foreign_device():
    store=Store();gateway=RobotGateway(store);token=set_actor('actor-a')
    try:
        with pytest.raises(PermissionError): gateway.status('b-device')
    finally: reset_actor(token)
