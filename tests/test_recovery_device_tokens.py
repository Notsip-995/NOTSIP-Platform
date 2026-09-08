from pathlib import Path
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
