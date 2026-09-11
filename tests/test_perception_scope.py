from types import SimpleNamespace
from notsip.perception_loop import ContinuousPerception


def test_continuous_perception_defaults_to_system_scope():
    settings=SimpleNamespace(data_dir='.',perception_enabled=False,vision_enabled=False,perception_screen_enabled=False)
    worker=ContinuousPerception(settings,None,None,None,None)
    assert worker.user_id=='system:desktop'
