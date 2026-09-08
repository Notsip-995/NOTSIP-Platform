from .app import app,settings,auth,pairing,nodes,recovery,store,agent,events,accounts,maintenance,DATA,native_voice,registry,intellect,memory_service
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
_require=__import__('notsip.app',fromlist=['require_auth']).require_auth
oauth.accounts=accounts
attach_recovery_runtime(store)
attach_product(app,require_auth=_require,settings=settings,auth=auth,pairing=pairing,nodes=nodes,recovery=recovery,store=store,agent=agent,events=events,accounts=accounts,maintenance=maintenance,DATA=DATA,native_voice=native_voice)
attach_completion(app,require_auth=_require,media=media,maintenance=maintenance,store=store,nodes=nodes,oauth=oauth,settings=settings,events=events,registry=registry,agent=agent)
attach_security_hardening(app)
attach_runtime_hardening(app,require_auth=_require,settings=settings,store=store,events=events,agent=agent)
attach_recovery_hardening(app,require_auth=_require,recovery=recovery,store=store)
attach_setup_hardening(app)
attach_approval_hardening(app,require_auth=_require,approvals=__import__('notsip.app',fromlist=['approvals']).approvals,registry=registry,audit_log=__import__('notsip.app',fromlist=['audit_log']).audit_log,agent=agent)
attach_voice_bridge(app,events,agent,native_voice)
attach_config_hardening(app)
attach_maintenance_hardening(maintenance)
attach_system_services(app,_require,settings,store,agent,registry)
install_state_hardening(store,jobs,app)
calendar_store=attach_calendar_service(app,_require,DATA,settings.local_timezone,agent,registry)
attach_information_fusion(app,_require,store,__import__('notsip.app',fromlist=['web']).web)
attach_perception(app,settings,win=__import__('notsip.app',fromlist=['win']).win,media=media,store=store,events=events,world=__import__('notsip.app',fromlist=['world']).world)
journal=EventJournal(DATA)
_original_publish=events.publish
async def _journaled_publish(event):journal.append(event);return await _original_publish(event)
events.publish=_journaled_publish
attach_event_reconstruction(app,_require,store,journal)
_health=HealthAnalytics(DATA)
attach_health_routes(app,_require,DATA)
attach_forensics(app,_require,DATA/'workspace')
attach_advanced_intelligence(app,_require,store,__import__('notsip.app',fromlist=['web']).web,agent,registry,events,settings)
attach_linux_routes(app,_require,agent,registry,settings)
event_reasoning=EventReasoningLoop(events,jobs).attach()
attach_background(app,store,nodes,recovery,intellect,events,memory_service,settings.health_interval,settings.checkpoint_interval,settings.proactive_interval,settings.memory_maintenance_interval,_health,_telemetry)
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
