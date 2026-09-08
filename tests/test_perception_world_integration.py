import asyncio
from types import SimpleNamespace
from pathlib import Path
from notsip.perception_loop import ContinuousPerception
from notsip.store import Store
from notsip.world import WorldModel


def test_perception_promotes_observation_into_world_model(tmp_path,monkeypatch):
    class FakeWindows:
        def screenshot(self,name):
            p=Path(name);p.parent.mkdir(parents=True,exist_ok=True);return {'status':'SUCCESS','path':str(p)}
    class FakeMedia:
        async def perceive(self,*args,**kwargs):return {'status':'SUCCESS','observation':'A dialog says READY','frame':'perception/f.png','timestamp':1}
    settings=SimpleNamespace(perception_enabled=True,vision_enabled=True,perception_screen_enabled=True,data_dir=str(tmp_path))
    monkeypatch.setattr('notsip.perception_loop.platform.system',lambda:'Windows')
    # Fake screenshot writes relative to workspace path used by the real implementation.
    (tmp_path/'workspace'/'perception').mkdir(parents=True)
    (tmp_path/'workspace'/'perception'/'desktop-latest.png').write_bytes(b'frame')
    class FakeWindows2:
        def screenshot(self,name):return {'status':'SUCCESS','path':name}
    perception=ContinuousPerception(settings,FakeWindows2(),FakeMedia(),Store(tmp_path),__import__('notsip.events',fromlist=['EventBus']).EventBus(),WorldModel(Store(tmp_path)))
    result=asyncio.run(perception.once())
    assert result['status']=='SUCCESS'
    entity=WorldModel(Store(tmp_path)).snapshot()['entities'][0]
    assert entity['id']=='computer:desktop'
    assert 'READY' in entity['data'] if isinstance(entity['data'],str) else 'READY' in entity['data']['observation']
