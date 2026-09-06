from .runtime_prod import app, media, settings, store, nodes, recovery, intellect, events, web, emailc, require_auth
from .streaming import attach as attach_streaming
from .background import attach as attach_background
from .routes_extra import attach as attach_extra
attach_streaming(app, media, settings, settings.api_key)
attach_background(app, store, nodes, recovery, intellect, events, settings.perception_interval)
attach_extra(app, require_auth, web, emailc)
__all__=['app']
