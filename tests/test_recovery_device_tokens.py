from notsip.background import BackgroundSupervisor
from notsip.nodes import NodeRegistry,RecoveryManager
from notsip.intelligence import Intelligence
from notsip.store import Store
from notsip.world import WorldModel
from notsip.events import EventBus


def test_scheduled_checkpoint_contains_device_token_hash(tmp_path):
    store=Store(tmp_path);token='device-secret';store.pair_device('android-1','Phone','android','',token)
    supervisor=BackgroundSupervisor(store,NodeRegistry(store,'secret'),RecoveryManager(tmp_path),Intelligence(store,WorldModel(store)),EventBus())
    rows=supervisor.recovery_devices()
    assert rows[0]['token_hash']
    assert rows[0]['token_hash'] != token


def test_recovery_restore_preserves_pending_device_commands(tmp_path):
    store=Store(tmp_path);token='device-secret';store.pair_device('android-1','Phone','android','',token)
    command_id=store.queue_command('android-1','notify',{'text':'hello'})
    state={'tasks':[],'devices':store.rows('SELECT id,name,platform,public_key,token_hash,last_seen,status,data FROM devices'),'commands':store.rows('SELECT id,device_id,action,payload,status,created,updated,result FROM commands'),'world':{'entities':[],'relations':[],'facts':[]},'timestamp':1}
    result=store.restore_runtime_state(state)
    assert result['commands']==1
    row=store.row('SELECT id,device_id,action,status,payload FROM commands WHERE id=?',(command_id,))
    assert row and row['device_id']=='android-1' and row['action']=='notify' and row['status']=='PENDING'
