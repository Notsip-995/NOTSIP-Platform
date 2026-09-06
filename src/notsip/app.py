from .runtime_prod import app, media, settings
from .streaming import attach
attach(app, media, settings, settings.api_key)
__all__=['app']
