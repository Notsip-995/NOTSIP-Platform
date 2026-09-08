from fastapi import Depends,HTTPException
from .actor_context import current_actor


def attach(app,require_auth,agent,settings):
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None)!='/api/remote/satellite']

    @app.get('/api/remote/satellite')
    async def satellite_route(bbox:str,start:str,end:str,scene_id:str='',_:None=Depends(require_auth)):
        # Satellite/remote-sensing access is an administrative capability. The
        # caller may not self-attest authorization through a query parameter.
        if current_actor()!='primary-user':
            raise HTTPException(403,'primary administrative actor required for satellite access')
        if not str(getattr(settings,'remote_sensing_url','')).strip() or not str(getattr(settings,'remote_sensing_token','')).strip():
            return {'status':'BLOCKED_BY_EXTERNAL_ENVIRONMENT','error':'authorized remote-sensing provider is not configured'}
        return await agent.run_tool('satellite_query',{
            'bbox':bbox,
            'start':start,
            'end':end,
            'scene_id':scene_id,
            'authorized':True,
        })
