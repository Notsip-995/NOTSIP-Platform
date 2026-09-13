from __future__ import annotations
import json,secrets,time
from fastapi import Depends,HTTPException,Request
from pydantic import BaseModel
from .actor_context import current_actor

_ALLOWED_COMMAND_STATUSES={'SUCCESS','FAILURE','PARTIAL_SUCCESS','UNKNOWN'}
MAX_COMMAND_RESULT_BYTES=1024*1024

class PairIn(BaseModel):
    code:str
    device_id:str
    name:str
    platform:str
    public_key:str=''


def _placeholder(store):return '%s' if getattr(store,'_backend',None) else '?'

def _device_auth(store,request:Request,device_id:str|None=None):
    did=(device_id or request.headers.get('X-NOTSIP-Device-ID','')).strip()
    token=request.headers.get('X-NOTSIP-Device-Token','').strip()
    if not did or not token or not store.device_token_valid(did,token):raise HTTPException(401,'device authentication required')
    row=store.row(f'SELECT status FROM devices WHERE id={_placeholder(store)}',(did,))
    if not row:raise HTTPException(404,'device not found')
    if str(row.get('status')).upper()=='REVOKED':raise HTTPException(403,'device is revoked')
    return did


_ALLOWED_QUEUE_ACTIONS={'open_url','open_app','notify','click_text','make_call','send_sms'}


def attach(app,require_auth,store,pairing,auth=None):
    from .database_concurrency_hardening import install as install_database_concurrency
    install_database_concurrency(store)
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in {'/api/pair/code','/api/pair/consume','/api/devices','/api/devices/{device_id}/commands','/api/devices/heartbeat','/api/devices/result'}]
    secret_store=getattr(auth,'secrets',None) if auth is not None else None
    if not getattr(store,'_notsip_pairing_ownership_guarded',False):
        original_pair_device=store.pair_device
        def guarded_pair_device(device_id,name,platform,public_key,token,owner=None):
            actor=str(owner or current_actor()).strip() or 'primary-user';device_owner=getattr(store,'device_owner',None);existing_owner=device_owner(device_id) if device_owner is not None else None
            if existing_owner is not None and existing_owner!=actor:raise PermissionError('device_id is already owned by another actor')
            return original_pair_device(device_id,name,platform,public_key,token,owner=actor)
        store.pair_device=guarded_pair_device;store._notsip_pairing_ownership_guarded=True

    if getattr(app,'get',None) is not None:
        @app.get('/api/pair/code')
        async def pair_code(_:None=Depends(require_auth)):
            actor=current_actor();code=store.create_pair_code()
            if secret_store is not None:secret_store.set('pairing:owner:'+code,{'actor':actor,'created_at':time.time(),'expires_at':time.time()+300})
            return {'code':code,'actor':actor,'expires_in':300}

        @app.get('/api/devices')
        async def devices(_:None=Depends(require_auth)):
            return {'devices':store.devices(current_actor())}

    @app.post('/api/devices/heartbeat')
    async def device_heartbeat(request:Request):
        did=_device_auth(store,request)
        store.heartbeat(did);return {'status':'ONLINE','device_id':did}

    @app.post('/api/devices/{device_id}/commands')
    async def queue_command(device_id:str,body:dict,_:None=Depends(require_auth)):
        p=_placeholder(store)
        if not store.row(f'SELECT id FROM devices WHERE id={p}',(device_id,)):raise HTTPException(404,'device not paired')
        action=str(body.get('action') or '').strip()
        if not action:raise HTTPException(400,'action is required')
        if action not in _ALLOWED_QUEUE_ACTIONS:raise HTTPException(400,f'unsupported action: {action}')
        command_id=store.queue_command(device_id,action,body.get('payload') or {})
        return {'status':'QUEUED','command_id':command_id,'device_id':device_id,'action':action}

    @app.post('/api/devices/result')
    async def device_result(body:dict,request:Request):
        did=_device_auth(store,request);command_id=str(body.get('command_id','')).strip()
        if not command_id:raise HTTPException(400,'command_id is required')
        p=_placeholder(store);command=store.row(f'SELECT device_id,status FROM commands WHERE id={p}',(command_id,))
        if not command:raise HTTPException(404,'command not found')
        if str(command.get('device_id'))!=did:raise HTTPException(403,'command does not belong to authenticated device')
        command_status=str(command.get('status','')).upper()
        if command_status!='DELIVERED':return {'status':'ALREADY_RECORDED','command_id':command_id,'command_status':command_status}
        status=str(body.get('status') or 'SUCCESS').upper()
        if status not in _ALLOWED_COMMAND_STATUSES:raise HTTPException(400,'invalid command result status')
        result=body.get('result') or {}
        if not isinstance(result,dict):raise HTTPException(400,'command result must be an object')
        if len(json.dumps(result,separators=(',',':'),default=str).encode('utf-8'))>MAX_COMMAND_RESULT_BYTES:raise HTTPException(413,'command result exceeds maximum size')
        ok=store.command_result(command_id,status,result,did)
        if not ok:raise HTTPException(409,'command result was not recorded for authenticated device')
        return {'status':'RECORDED','command_id':command_id,'device_id':did}

    if getattr(app,'get',None) is not None:
        @app.get('/api/devices/{device_id}/commands')
        async def commands(device_id:str,request:Request):
            did=_device_auth(store,request,device_id)
            return {'commands':store.pull_commands(did)}

    # Registered last so single-post mocks capture the pairing handler.
    @app.post('/api/pair/consume')
    async def pair_consume(body:PairIn,request:Request,_:None=Depends(require_auth)):
        actor=current_actor();code=body.code.strip().upper()
        if secret_store is not None:
            record=secret_store.get('pairing:owner:'+code);expires=float(record.get('expires_at',0)) if isinstance(record,dict) else 0
            if not isinstance(record,dict) or str(record.get('actor'))!=actor or expires<=time.time():raise HTTPException(403,'pairing code is not owned by current actor or has expired')
            existing_owner=store.device_owner(body.device_id)
            if existing_owner is not None and existing_owner!=actor:raise HTTPException(409,'device_id is already owned by another actor')
        consume=getattr(pairing,'consume_code',None) or store.consume_pair_code
        if not consume(code):raise HTTPException(400,'invalid or expired pairing code')
        if secret_store is not None:secret_store.delete('pairing:owner:'+code)
        token=secrets.token_urlsafe(32);store.pair_device(body.device_id,body.name,body.platform,body.public_key,token,owner=actor)
        return {'paired':True,'status':'PAIRED','device_id':body.device_id,'token':token,'device_token':token,'actor':actor}
