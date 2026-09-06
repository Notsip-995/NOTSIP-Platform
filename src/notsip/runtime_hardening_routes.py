from __future__ import annotations
import hashlib, hmac, json, uuid
from fastapi import Depends, Header, HTTPException, Request
from .events import Event

def attach(app, *, require_auth, settings, store, events):
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in {'/api/devices/result','/api/events'}]

    @app.post('/api/devices/result')
    async def device_result(request: Request, payload: dict):
        device_id=request.headers.get('X-NOTSIP-Device-ID','')
        token=request.headers.get('X-NOTSIP-Device-Token','')
        if not device_id or not token or not store.device_token_valid(device_id,token):
            raise HTTPException(401,'device authentication required')
        command_id=str(payload.get('command_id',''))
        if not command_id or not store.row('SELECT id FROM commands WHERE id=? AND device_id=?',(command_id,device_id)):
            raise HTTPException(404,'command not found for authenticated device')
        ok=store.command_result(command_id,str(payload.get('status','UNKNOWN')),payload.get('result') or {},device_id)
        if not ok:raise HTTPException(409,'command result was not recorded')
        return {'status':'RECORDED','device_id':device_id,'command_id':command_id}

    @app.post('/api/events')
    async def event_ingest(payload: dict, x_notsip_signature: str=Header(default=''), _:None=Depends(require_auth)):
        if settings.event_hmac_secret:
            raw=json.dumps(payload,separators=(',',':'),sort_keys=True).encode();expected=hmac.new(settings.event_hmac_secret.encode(),raw,hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected,x_notsip_signature):raise HTTPException(401,'invalid event signature')
        await events.publish(Event(payload.get('type','external'),payload,'external'))
        return {'status':'ACCEPTED','event_id':str(uuid.uuid4()),'published':True}
