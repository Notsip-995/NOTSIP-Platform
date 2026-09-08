from fastapi import Depends,HTTPException
from .health_analytics import HealthAnalytics
from .system_services import _telemetry
from .actor_context import current_actor

def attach(app, require_auth, root):
    analytics=HealthAnalytics(root)
    def require_admin():
        if current_actor()!='primary-user':raise HTTPException(403,'primary administrative actor required')
    @app.get('/api/maintenance/health')
    async def health_summary(_:None=Depends(require_auth)):
        require_admin();return analytics.analyze()
    @app.get('/api/maintenance/telemetry/history')
    async def telemetry_history(limit:int=120,_:None=Depends(require_auth)):
        require_admin();return {'samples':analytics.samples(limit)}
