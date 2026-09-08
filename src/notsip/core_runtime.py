from .app import app,settings,auth,pairing,nodes,recovery,store,agent,events,accounts,maintenance,DATA,native_voice,registry,intellect,memory_service,backups,web,emailc,policy
from .runtime_prod import oauth, media, jobs
from .product_routes import attach as attach_product
from .completion_routes import attach as attach_completion
from .security_hardening import attach as attach_security_hardening
from .runtime_hardening_routes import attach as attach_runtime_hardening
from .recovery_hardening import attach as attach_recovery_hardening
from .recovery_runtime import attach as attach_recovery_runtime
from .setup_hardening import attach as attach_setup_hardening
from .approval_hardening import attach as attach_approval_hardening
from .voice_bridge import attach as attach_voice_bridge
from .config_hardening import attach as attach_config_hardening
from .maintenance_hardening import attach as attach_maintenance_hardening
from .route_integrity import normalize as normalize_routes
from .system_services import attach as attach_system_services, _telemetry
from .state_hardening import install as install_state_hardening
from .calendar_service import attach as attach_calendar_service
from .information_fusion import attach as attach_information_fusion
from .event_reconstruction import attach as attach_event_reconstruction
from .perception_loop import attach as attach_perception
from .background import attach as attach_background
from .health_analytics import HealthAnalytics
from .health_routes import attach as attach_health_routes
from .forensics import attach as attach_forensics
from .event_journal import EventJournal
from .advanced_intelligence import attach as attach_advanced_intelligence
from .event_reasoning_loop import EventReasoningLoop
from .linux_routes import attach as attach_linux_routes
from .sensor_ingress import attach as attach_sensor_ingress
from .business_routes import attach as attach_business_routes
from .actor_context import attach_actor_middleware
from .session_hardening import attach as attach_session_hardening
from .task_hardening import attach as attach_task_hardening
from .pairing_hardening import attach as attach_pairing_hardening
from .windows_hardening import attach as attach_windows_hardening
from .distributed_failover import attach as attach_distributed_failover
from .oidc_hardening import attach as attach_oidc_hardening
from .audit_hardening import attach as attach_audit_hardening
from .audit_scope_hardening import attach as attach_audit_scope_hardening
from .notification_hardening import attach as attach_notification_hardening
from .notifications import NotificationStore
from .backup_hardening import install as install_backup_hardening
from .external_domains import attach as attach_external_domains
from .recovery_state_hardening import install_checkpoint_wrapper
from .status_scope_hardening import attach as attach_status_scope_hardening
from .browser_hardening import attach as attach_browser_hardening
from .database_router import attach as attach_database_router
from .threat_assessment import ThreatAssessor
from .workspace_scope_hardening import attach as attach_workspace_scope_hardening
from fastapi import Depends,HTTPException
from .actor_context import current_actor
from .tools import Tool
from .policy import Risk
from .execution_gate import ToolExecutionGate
_require=__import__('notsip.app',fromlist=['require_auth']).require_auth
oauth.accounts=accounts
jobs.events=events
nodes.world=__import__('notsip.app',fromlist=['world']).world
app.CONFIG_SECRET_NAMES.add('business_admin_token');app.CONFIG_HIGH_RISK.add('business_admin_token')
app.CONFIG_SECRET_NAMES.add('speaker_identity_token');app.CONFIG_HIGH_RISK.add('speaker_identity_token')
from .product_layer import ConfigStore
ConfigStore.SECRET_NAMES.add('business_admin_token');ConfigStore.SECRET_NAMES.add('speaker_identity_token')
install_backup_hardening(backups)
external_domains=attach_external_domains(registry,settings)
install_checkpoint_wrapper(recovery,DATA)
attach_recovery_runtime(store)
attach_product(app,require_auth=_require,settings=settings,auth=auth,pairing=pairing,nodes=nodes,recovery=recovery,store=store,agent=agent,events=events,accounts=accounts,maintenance=maintenance,DATA=DATA,native_voice=native_voice)
attach_completion(app,require_auth=_require,media=media,maintenance=maintenance,store=store,nodes=nodes,oauth=oauth,settings=settings,events=events,registry=registry,agent=agent)
attach_security_hardening(app)
attach_runtime_hardening(app,require_auth=_require,settings=settings,store=store,events=events,agent=agent)
attach_recovery_hardening(app,require_auth=_require,recovery=recovery,store=store)
attach_setup_hardening(app)
attach_approval_hardening(app,require_auth=_require,approvals=__import__('notsip.app',fromlist=['approvals']).approvals,registry=registry,audit_log=__import__('notsip.app',fromlist=['audit_log']).audit_log,agent=agent)
attach_voice_bridge(app,events,agent,native_voice,settings)
attach_config_hardening(app)
attach_maintenance_hardening(maintenance)
attach_system_services(app,_require,settings,store,agent,registry)
install_state_hardening(store,jobs,app)
calendar_store=attach_calendar_service(app,_require,DATA,settings.local_timezone,agent,registry)
attach_information_fusion(app,_require,store,web)
attach_perception(app,settings,win=__import__('notsip.app',fromlist=['win']).win,media=media,store=store,events=events,world=__import__('notsip.app',fromlist=['world']).world)
sensor_world=__import__('notsip.app',fromlist=['world']).world
attach_sensor_ingress(app,store,sensor_world,events)
journal=EventJournal(DATA)
_original_publish=events.publish
async def _journaled_publish(event):journal.append(event);return await _original_publish(event)
events.publish=_journaled_publish
attach_event_reconstruction(app,_require,store,journal)
_health=HealthAnalytics(DATA)
attach_health_routes(app,_require,DATA)
attach_forensics(app,_require,DATA/'workspace')
attach_advanced_intelligence(app,_require,store,web,agent,registry,events,settings)
attach_linux_routes(app,_require,agent,registry,settings)
attach_business_routes(app,_require,agent,registry,events,settings) if False else attach_business_routes(app,_require,agent,registry,settings)
attach_actor_middleware(app,auth)
attach_session_hardening(app,_require,agent,DATA)
attach_task_hardening(app,_require,store,jobs)
attach_pairing_hardening(app,_require,store,pairing,auth)
attach_windows_hardening(registry,__import__('notsip.app',fromlist=['win']).win)
attach_distributed_failover(events,store)
attach_oidc_hardening(app,auth,accounts,settings)
attach_audit_hardening(app,_require,audit_log)
attach_audit_scope_hardening(app,_require,store,audit_log)
notifications=NotificationStore(DATA,store)
attach_notification_hardening(app,events,notifications,_require)
attach_status_scope_hardening(app,_require,store,policy,agent,settings,registry,web,emailc,auth)
attach_browser_hardening(app,_require,agent,browser,registry)
attach_database_router(app,_require,agent,registry)
_threat=ThreatAssessor()
if registry.get('assess_threat') is None:registry.add(Tool('assess_threat','Assess supplied security indicators without performing containment.','SECURITY_MONITORING',Risk.LOW,{'type':'object','properties':{'indicators':{'type':'array','items':{'type':'object'}}}},_threat.assess))
ToolExecutionGate.wrap_registry(registry)
@app.post('/api/security/threat-assessment')
async def threat_assessment(payload:dict,_:None=Depends(_require)):
    indicators=payload.get('indicators') or []
    if not isinstance(indicators,list):raise HTTPException(400,'indicators must be an array')
    result=_threat.assess(indicators);result['actor']=current_actor();return result
attach_workspace_scope_hardening(app,registry,DATA)
event_reasoning=EventReasoningLoop(events,jobs).attach()
attach_background(app,store,nodes,recovery,intellect,events,memory_service,settings.health_interval,settings.checkpoint_interval,settings.proactive_interval,settings.memory_maintenance_interval,_health,_telemetry)
@app.get('/healthz',include_in_schema=False)
async def healthz(request):
    host=getattr(getattr(request,'client',None),'host','')
    if host not in {'127.0.0.1','::1','localhost'}:from fastapi import HTTPException;raise HTTPException(404,'not found')
    return {'status':'ok','identity':'NOTSIP','version':__import__('notsip').__version__}
normalize_routes(app)

@app.on_event('startup')
async def start_configured_native_voice():
    if getattr(settings,'native_voice_enabled',False):
        result=native_voice.start()
        if result.get('status') not in {'STARTED','ALREADY_RUNNING','UNAVAILABLE'}:raise RuntimeError(f'Unexpected native voice startup result: {result}')

@app.on_event('shutdown')
async def stop_configured_native_voice():
    if getattr(native_voice,'running',False):native_voice.stop()

__all__=['app']
