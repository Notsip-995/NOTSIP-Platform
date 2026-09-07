from .app import app,settings,auth,pairing,nodes,recovery,store,agent,events,accounts,maintenance,DATA,native_voice
from .runtime_prod import oauth, media
from .product_routes import attach as attach_product
from .completion_routes import attach as attach_completion
from .security_hardening import attach as attach_security_hardening
from .runtime_hardening_routes import attach as attach_runtime_hardening
from .recovery_hardening import attach as attach_recovery_hardening
from .setup_hardening import attach as attach_setup_hardening
from .approval_hardening import attach as attach_approval_hardening
from .voice_bridge import attach as attach_voice_bridge
_require=__import__('notsip.app',fromlist=['require_auth']).require_auth
oauth.accounts=accounts
attach_product(app,require_auth=_require,settings=settings,auth=auth,pairing=pairing,nodes=nodes,recovery=recovery,store=store,agent=agent,events=events,accounts=accounts,maintenance=maintenance,DATA=DATA,native_voice=native_voice)
attach_completion(app,require_auth=_require,media=media,maintenance=maintenance,store=store,nodes=nodes,oauth=oauth,settings=settings,events=events)
attach_security_hardening(app)
attach_runtime_hardening(app,require_auth=_require,settings=settings,store=store,events=events)
attach_recovery_hardening(app,require_auth=_require,recovery=recovery,store=store)
attach_setup_hardening(app)
attach_approval_hardening(app,require_auth=_require,approvals=__import__('notsip.app',fromlist=['approvals']).approvals,registry=__import__('notsip.app',fromlist=['registry']).registry,audit_log=__import__('notsip.app',fromlist=['audit_log']).audit_log)
attach_voice_bridge(app,events,agent)
__all__=['app']
