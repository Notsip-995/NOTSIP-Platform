from __future__ import annotations
from fastapi import Depends,HTTPException
from .actor_context import current_actor


def attach(app,events,notifications,require_auth):
    async def on_candidate(event):
        payload=dict(event.payload or {});actor=str(payload.get('actor') or 'primary-user')
        body=str(payload.get('memory') or payload.get('reason') or 'NOTSIP identified a relevant event.')
        priority=str(payload.get('priority') or 'IMPORTANT')
        notifications.create(actor,'NOTSIP proactive notification',body,priority,payload.get('reason',''),event.source,dedupe_key=f"{actor}:{payload.get('type','proactive')}:{body}")
    events.on('proactive.candidate',on_candidate)
    router=getattr(app,'router',None)
    if router is not None:
        router.routes=[r for r in router.routes if getattr(r,'path',None) not in {'/api/notifications','/api/notifications/{notification_id}/ack'}]
    get_route=getattr(app,'get',None);post_route=getattr(app,'post',None)
    if get_route is None or post_route is None:return
    @get_route('/api/notifications')
    async def list_notifications(include_ack:bool=False,limit:int=100,_:None=Depends(require_auth)):
        return {'notifications':notifications.list(current_actor(),include_ack,limit)}
    @post_route('/api/notifications/{notification_id}/ack')
    async def ack_notification(notification_id:str,_:None=Depends(require_auth)):
        item=notifications.acknowledge(current_actor(),notification_id)
        if not item:raise HTTPException(404,'notification not found')
        return item
