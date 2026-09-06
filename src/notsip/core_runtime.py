from .app import app,settings,auth,pairing,nodes,recovery,store,agent,events,accounts,maintenance,DATA,native_voice
from .runtime_prod import oauth, media
from .product_routes import attach as attach_product
from .completion_routes import attach as attach_completion
from .security_hardening import attach as attach_security_hardening
_require=__import__('notsip.app',fromlist=['require_auth']).require_auth
attach_product(app,require_auth=_require,settings=settings,auth=auth,pairing=pairing,nodes=nodes,recovery=recovery,store=store,agent=agent,events=events,accounts=accounts,maintenance=maintenance,DATA=DATA,native_voice=native_voice)
attach_completion(app,require_auth=_require,media=media,maintenance=maintenance,store=store,nodes=nodes,oauth=oauth,settings=settings)
attach_security_hardening(app)
__all__=['app']
