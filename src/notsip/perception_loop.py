from __future__ import annotations
import asyncio,hashlib,platform,time
from pathlib import Path

class ContinuousPerception:
    def __init__(self,settings,windows,media,store,events,world=None,user_id='system:desktop'):
        self.settings=settings;self.windows=windows;self.media=media;self.store=store;self.events=events;self.world=world;self.user_id=user_id;self.last_hash='';self.running=True;self.last_observation=0.0
    async def once(self):
        if not getattr(self.settings,'perception_enabled',False) or not getattr(self.settings,'vision_enabled',False):return {'status':'DISABLED'}
        if not getattr(self.settings,'perception_screen_enabled',False):return {'status':'DISABLED','reason':'screen perception disabled'}
        if platform.system()!='Windows':return {'status':'SKIPPED','reason':'Windows node required'}
        result=self.windows.screenshot('perception/desktop-latest.png');p=Path(self.settings.data_dir)/'workspace'/result['path'];raw=p.read_bytes();digest=hashlib.sha256(raw).hexdigest()
        if digest==self.last_hash:return {'status':'UNCHANGED','frame':result['path'],'sha256':digest}
        self.last_hash=digest;self.last_observation=time.time()
        obs=await self.media.perceive(raw,'Describe only visible desktop evidence. Identify UI state changes, errors, dialogs, and actionable facts without guessing.','image/png');text=str(obs.get('observation',''))
        provenance={'sha256':digest,'timestamp':self.last_observation,'frame':obs.get('frame'),'source':'desktop-vision','scope':'system:desktop'}
        self.store.remember(self.user_id,'perception',text,.65,'desktop-vision',provenance)
        self.store.fact(text,'desktop-vision',obs.get('frame',''),.65,provenance)
        if self.world is not None:self.world.upsert('computer:desktop','screen','Primary desktop',{'observation':text,'frame':obs.get('frame'),'sha256':digest,'observed_at':self.last_observation},owner=None)
        from .events import Event
        event_payload=dict(obs);event_payload.update({'sha256':digest,'observed_at':self.last_observation,'world_entity':'computer:desktop','scope':'system:desktop'})
        await self.events.publish(Event('perception.observed',event_payload,'desktop-perception'));return event_payload
    async def loop(self,interval=None):
        delay=max(2,int(interval or getattr(self.settings,'perception_interval',10)))
        while self.running:
            try:await self.once()
            except Exception as exc:
                from .events import Event
                await self.events.publish(Event('perception.error',{'error':str(exc)},'desktop-perception'))
            await asyncio.sleep(delay)
    def stop(self):self.running=False

def attach(app,settings,windows,media,store,events,world=None):
    loop=ContinuousPerception(settings,windows,media,store,events,world)
    @app.on_event('startup')
    async def start_perception():app.state.perception_task=asyncio.create_task(loop.loop())
    @app.on_event('shutdown')
    async def stop_perception():loop.stop();task=getattr(app.state,'perception_task',None);task and task.cancel()
