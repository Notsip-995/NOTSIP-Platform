from __future__ import annotations
import asyncio,time
from .events import Event
from .event_priority import EventPriorityEngine
from .predictive_maintenance import PredictiveMaintenance
class BackgroundSupervisor:
    def __init__(self,store,nodes,recovery,intellect,events,memory=None,health_interval=15,checkpoint_interval=300,proactive_interval=60,memory_interval=900,health_analytics=None,telemetry=None,priority_engine=None,predictor=None):
        self.store=store;self.nodes=nodes;self.recovery=recovery;self.intellect=intellect;self.events=events;self.memory=memory;self.health_interval=max(5,int(health_interval));self.checkpoint_interval=max(30,int(checkpoint_interval));self.proactive_interval=max(15,int(proactive_interval));self.memory_interval=max(60,int(memory_interval));self.health_analytics=health_analytics;self.telemetry=telemetry;self.priority=priority_engine or EventPriorityEngine();self.predictor=predictor or PredictiveMaintenance();self.running=True;self.next_checkpoint=0;self.next_proactive=0;self.next_memory=0
    def recovery_devices(self):
        try:return self.store.rows('SELECT id,name,platform,public_key,token_hash,last_seen,status,data FROM devices')
        except Exception:return self.store.devices()
    def recovery_commands(self):
        try:return self.store.rows('SELECT id,device_id,action,payload,status,created,updated,result FROM commands')
        except Exception:return []
    async def _health_cycle(self):
        if not (self.telemetry and self.health_analytics):return
        analysis=self.health_analytics.analyze(120);snapshot=self.telemetry();self.health_analytics.record(snapshot)
        if analysis.get('warnings'):await self.events.publish(Event('health.warning',analysis,'health-analytics'))
        history=self.health_analytics.samples(120)
        cpu=self.predictor.evaluate(history,'cpu_percent',warning_slope=.5,failure_threshold=95)
        mem=self.predictor.evaluate([{'memory_percent':(r.get('memory') or {}).get('percent')} for r in history],'memory_percent',warning_slope=.5,failure_threshold=95)
        for prediction in (cpu,mem):
            if prediction.get('status')=='SUCCESS' and prediction.get('trend',{}).get('state') in {'DEGRADATION','ANOMALY','PREDICTED_FAILURE'}:await self.events.publish(Event('maintenance.prediction',prediction,'predictive-maintenance'))
    async def loop(self):
        while self.running:
            now=time.time()
            try:
                node_state=self.nodes.reconcile();await self._health_cycle()
                if now>=self.next_checkpoint:
                    self.recovery.checkpoint({'timestamp':now,'devices':self.recovery_devices(),'commands':self.recovery_commands(),'tasks':self.store.tasks(),'world':self.intellect.world.snapshot()});self.next_checkpoint=now+self.checkpoint_interval
                if now>=self.next_proactive:
                    candidates=self.intellect.trigger_candidates()
                    for candidate in candidates[:10]:
                        decision=self.priority.classify(importance=.7,urgency=.3,relevance=.9,event_type=candidate.get('type','proactive'))
                        if decision.priority.value>=2:
                            payload=dict(candidate);payload.update({'priority':decision.priority.name,'interrupt':decision.interrupt,'score':decision.score});await self.events.publish(Event('proactive.candidate',payload,'intelligence'))
                    self.next_proactive=now+self.proactive_interval
                if now>=self.next_memory and self.memory:self.memory.decay();self.memory.consolidate();self.next_memory=now+self.memory_interval
                stale=[n for n in node_state if n['status']=='STALE']
                if stale:await self.events.publish(Event('nodes.stale',{'nodes':stale},'federation'))
            except Exception as exc:await self.events.publish(Event('supervisor.error',{'error':str(exc)},'runtime'))
            await asyncio.sleep(self.health_interval)
    def stop(self):self.running=False

def attach(app,store,nodes,recovery,intellect,events,memory=None,health_interval=15,checkpoint_interval=300,proactive_interval=60,memory_interval=900,health_analytics=None,telemetry=None,priority_engine=None,predictor=None):
    supervisor=BackgroundSupervisor(store,nodes,recovery,intellect,events,memory,health_interval,checkpoint_interval,proactive_interval,memory_interval,health_analytics,telemetry,priority_engine,predictor)
    @app.on_event('startup')
    async def start_supervisor():app.state.supervisor=asyncio.create_task(supervisor.loop())
    @app.on_event('shutdown')
    async def stop_supervisor():supervisor.stop();task=getattr(app.state,'supervisor',None);task and task.cancel()
