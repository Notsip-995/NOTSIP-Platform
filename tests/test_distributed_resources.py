from notsip.resource_router import ResourceRouter, RobotGateway
from notsip.store import Store


def test_resource_router_selects_healthy_capable_node(tmp_path):
    store=Store(tmp_path);store.pair_device('local','Local','local','', 'token-local');store.exec('UPDATE devices SET data=? WHERE id=?',('{"capabilities":["GPU","DATA_PROCESSING"]}', 'local'))
    result=ResourceRouter(store).select('GPU')
    assert result['status']=='SUCCESS'
    assert result['node']['id']=='local'


def test_resource_router_fails_closed_without_capability(tmp_path):
    result=ResourceRouter(Store(tmp_path)).select('ROBOTICS')
    assert result['status']=='BLOCKED_BY_EXTERNAL_ENVIRONMENT'


def test_robot_gateway_requires_control_authorization(tmp_path):
    store=Store(tmp_path);store.pair_device('r1','Robot','robotics','', 'token');store.exec('UPDATE devices SET data=? WHERE id=?',('{"robot_capabilities":["status"]}', 'r1'))
    result=RobotGateway(store).command('r1','move',{'x':1})
    assert result['status']=='FAILURE'


def test_robot_gateway_queues_authorized_command(tmp_path):
    store=Store(tmp_path);store.pair_device('r1','Robot','robotics','', 'token');store.exec('UPDATE devices SET data=? WHERE id=?',('{"robot_capabilities":["control"]}', 'r1'))
    result=RobotGateway(store).command('r1','move',{'x':1})
    assert result['status']=='QUEUED'
    assert result['command_id']
