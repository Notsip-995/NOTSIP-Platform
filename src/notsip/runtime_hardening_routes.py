from __future__ import annotations
import hashlib,hmac,json,uuid
from fastapi import Depends,Header,HTTPException,Request
from .events import Event

def attach(app, *, require_auth, settings, store, events, agent=None):
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in {'/api/devices/result','/api/devices/{device_id}/commands','/api/devices/heartbeat','/api/events','/api/healthz'}]
    if agent is not None:
        app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in {'/api/windows/click','/api/windows/type','/api/windows/hotkey','/api/devices/{device_id}/commands'}]
    def _device(request:Request):
        device_id=request.headers.get('X-NOTSIP-Device-ID','').strip();token=request.headers.get('X-NOTSIP-Device-Token','').strip()
        if not device_id or not token or not store.device_token_valid(device_id,token):raise HTTPException(401,'device authentication required')
        return device_id
    @app.get('/api/healthz',include_in_schema=False)
    async def healthz(request:Request):
        client=request.client.host if request.client else ''
        if client not in {'127.0.0.1','::1'}:raise HTTPException(403,'local health probe only')
        return {'status':'ok','identity':'NOTSIP','version':'0.9.0'}
    @app.post('/api/devices/heartbeat')
    async def device_heartbeat(request:Request):
        device_id=_device(request);store.heartbeat(device_id,'ONLINE');return {'status':'SUCCESS','device_id':device_id}
    @app.get('/api/devices/{device_id}/commands')
    async def device_commands(device_id:str,request:Request):
        authenticated=_device(request)
        if authenticated!=device_id:raise HTTPException(403,'device identity mismatch')
        return {'commands':store.pull_commands(device_id)}
    @app.post('/api/devices/{device_id}/commands')
    async def queue_device_command(device_id:str,payload:dict,_:None=Depends(require_auth)):
        if not store.row('SELECT id FROM devices WHERE id=?',(device_id,)):raise HTTPException(404,'device not found')
        action=str(payload.get('action','')).strip()
        if not action:raise HTTPException(400,'action is required')
        if agent is not None:
            result=await agent.run_tool('android_command',{'device_id':device_id,'action':action,'payload':payload.get('payload') or {}})
            return result
        command_id=store.queue_command(device_id,action,payload.get('payload') or {})
        return {'status':'QUEUED','command_id':command_id,'device_id':device_id,'action':action}
    @app.post('/api/devices/result')
    async def device_result(request:Request,payload:dict):
        device_id=_device(request);command_id=str(payload.get('command_id',''))
        if not command_id or not store.row('SELECT id FROM commands WHERE id=? AND device_id=?',(command_id,device_id)):raise HTTPException(404,'command not found for authenticated device')
        ok=store.command_result(command_id,str(payload.get('status','UNKNOWN')),payload.get('result') or {},device_id)
        if not ok:raise HTTPException(409,'command result was not recorded')
        return {'status':'RECORDED','device_id':device_id,'command_id':command_id}
    @app.post('/api/events')
    async def event_ingest(payload:dict,x_notsip_signature:str=Header(default=''),_:None=Depends(require_auth)):
        if settings.event_hmac_secret:
            raw=json.dumps(payload,separators=(',',':'),sort_keys=True).encode();expected=hmac.new(settings.event_hmac_secret.encode(),raw,hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected,x_notsip_signature):raise HTTPException(401,'invalid event signature')
        errors=await events.publish(Event(payload.get('type','external'),payload,'external'))
        return {'status':'ACCEPTED' if not errors else 'PARTIAL_SUCCESS','event_id':str(uuid.uuid4()),'published':True,'handler_errors':errors}
    if agent is not None:
        @app.post('/api/windows/click')
        async def windows_click(payload:dict,_:None=Depends(require_auth)):return await agent.run_tool('windows_click',payload)
        @app.post('/api/windows/type')
        async def windows_type(payload:dict,_:None=Depends(require_auth)):return await agent.run_tool('windows_type',payload)
        @app.post('/api/windows/hotkey')
        async def windows_hotkey(payload:dict,_:None=Depends(require_auth)):return await agent.run_tool('windows_hotkey',{'keys':payload.get('keys') or []})
