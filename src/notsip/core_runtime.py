from .app import app,settings,auth,pairing,nodes,recovery,store,agent,events,accounts,maintenance,DATA,native_voice
from .runtime_prod import oauth, media
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
_require=__import__('notsip.app',fromlist=['require_auth']).require_auth
oauth.accounts=accounts
attach_recovery_runtime(store)
attach_product(app,require_auth=_require,settings=settings,auth=auth,pairing=pairing,nodes=nodes,recovery=recovery,store=store,agent=agent,events=events,accounts=accounts,maintenance=maintenance,DATA=DATA,native_voice=native_voice)
attach_completion(app,require_auth=_require,media=media,maintenance=maintenance,store=store,nodes=nodes,oauth=oauth,settings=settings,events=events)
attach_security_hardening(app)
attach_runtime_hardening(app,require_auth=_require,settings=settings,store=store,events=events)
attach_recovery_hardening(app,require_auth=_require,recovery=recovery,store=store)
attach_setup_hardening(app)
attach_approval_hardening(app,require_auth=_require,approvals=__import__('notsip.app',fromlist=['approvals']).approvals,registry=__import__('notsip.app',fromlist=['registry']).registry,audit_log=__import__('notsip.app',fromlist=['audit_log']).audit_log)
attach_voice_bridge(app,events,agent)
attach_config_hardening(app)
attach_maintenance_hardening(maintenance)
normalize_routes(app)

@app.on_event('startup')
async def start_configured_native_voice():
    if getattr(settings, 'native_voice_enabled', False):
        result=native_voice.start()
        if result.get('status') not in {'STARTED','ALREADY_RUNNING','UNAVAILABLE'}:
            raise RuntimeError(f'Unexpected native voice startup result: {result}')

@app.on_event('shutdown')
async def stop_configured_native_voice():
    if getattr(native_voice, 'running', False):
        native_voice.stop()

__all__=['app']
