from __future__ import annotations
import asyncio,time
class BackgroundSupervisor:
    def __init__(self,store,nodes,recovery,intellect,events,memory=None,health_interval=15,checkpoint_interval=300,proactive_interval=60,memory_interval=900):
        self.store=store;self.nodes=nodes;self.recovery=recovery;self.intellect=intellect;self.events=events;self.memory=memory;self.health_interval=max(5,int(health_interval));self.checkpoint_interval=max(30,int(checkpoint_interval));self.proactive_interval=max(15,int(proactive_interval));self.memory_interval=max(60,int(memory_interval));self.running=True;self.next_checkpoint=0;self.next_proactive=0;self.next_memory=0
    async def loop(self):
        while self.running:
            now=time.time()
            try:
                node_state=self.nodes.reconcile()
                if now>=self.next_checkpoint:
                    self.recovery.checkpoint({'timestamp':now,'devices':self.store.devices(),'tasks':self.store.tasks(),'world':self.intellect.world.snapshot()});self.next_checkpoint=now+self.checkpoint_interval
                if now>=self.next_proactive:
                    candidates=self.intellect.trigger_candidates()
                    if candidates:await self.events.publish(__import__('notsip.events',fromlist=['Event']).Event('proactive.candidates',{'count':len(candidates),'candidates':candidates[:10]},'intelligence'))
                    self.next_proactive=now+self.proactive_interval
                if now>=self.next_memory and self.memory:
                    self.memory.decay();self.memory.consolidate();self.next_memory=now+self.memory_interval
                stale=[n for n in node_state if n['status']=='STALE']
                if stale:await self.events.publish(__import__('notsip.events',fromlist=['Event']).Event('nodes.stale',{'nodes':stale},'federation'))
            except Exception as exc:await self.events.publish(__import__('notsip.events',fromlist=['Event']).Event('supervisor.error',{'error':str(exc)},'runtime'))
            await asyncio.sleep(self.health_interval)
    def stop(self):self.running=False

def attach(app,store,nodes,recovery,intellect,events,memory=None,health_interval=15,checkpoint_interval=300,proactive_interval=60,memory_interval=900):
    supervisor=BackgroundSupervisor(store,nodes,recovery,intellect,events,memory,health_interval,checkpoint_interval,proactive_interval,memory_interval)
    @app.on_event('startup')
    async def start_supervisor():app.state.supervisor=asyncio.create_task(supervisor.loop())
    @app.on_event('shutdown')
    async def stop_supervisor():supervisor.stop();task=getattr(app.state,'supervisor',None);task and task.cancel()
