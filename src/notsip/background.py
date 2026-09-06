from __future__ import annotations
import asyncio, time
class BackgroundSupervisor:
    def __init__(self,store,nodes,recovery,intellect,events,interval=60):self.store=store;self.nodes=nodes;self.recovery=recovery;self.intellect=intellect;self.events=events;self.interval=max(10,int(interval));self.running=True
    async def loop(self):
        while self.running:
            try:
                node_state=self.nodes.reconcile();
                self.recovery.checkpoint({'timestamp':time.time(),'devices':self.store.devices(),'tasks':self.store.tasks(),'world':self.intellect.world.snapshot()})
                candidates=self.intellect.trigger_candidates()
                if candidates:await self.events.publish(__import__('notsip.events',fromlist=['Event']).Event('proactive.candidates',{'count':len(candidates),'candidates':candidates[:10]},'intelligence'))
                stale=[n for n in node_state if n['status']=='STALE']
                if stale:await self.events.publish(__import__('notsip.events',fromlist=['Event']).Event('nodes.stale',{'nodes':stale},'federation'))
            except Exception as exc: await self.events.publish(__import__('notsip.events',fromlist=['Event']).Event('supervisor.error',{'error':str(exc)},'runtime'))
            await asyncio.sleep(self.interval)
    def stop(self):self.running=False

def attach(app,store,nodes,recovery,intellect,events,interval=60):
    supervisor=BackgroundSupervisor(store,nodes,recovery,intellect,events,interval)
    @app.on_event('startup')
    async def start_supervisor():app.state.supervisor=asyncio.create_task(supervisor.loop())
    @app.on_event('shutdown')
    async def stop_supervisor():
        supervisor.stop();task=getattr(app.state,'supervisor',None)
        if task:task.cancel()
