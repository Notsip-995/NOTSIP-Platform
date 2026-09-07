from fastapi import Depends
from .health_analytics import HealthAnalytics
from .system_services import _telemetry

def attach(app, require_auth, root):
    analytics=HealthAnalytics(root)
    @app.get('/api/maintenance/health')
    async def health_summary(_:None=Depends(require_auth)):
        return analytics.analyze()
    @app.get('/api/maintenance/telemetry/history')
    async def telemetry_history(limit:int=120,_:None=Depends(require_auth)):
        return {'samples':analytics.samples(limit)}
