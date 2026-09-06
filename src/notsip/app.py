from .runtime_prod import app, media, settings, store, nodes, recovery, intellect, events
from .streaming import attach as attach_streaming
from .background import attach as attach_background
attach_streaming(app, media, settings, settings.api_key)
attach_background(app, store, nodes, recovery, intellect, events, settings.perception_interval)
__all__=['app']
