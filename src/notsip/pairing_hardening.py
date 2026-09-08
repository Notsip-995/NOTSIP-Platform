from __future__ import annotations
import hashlib
import secrets
from fastapi import Depends,HTTPException,Request
from pydantic import BaseModel
from .actor_context import current_actor

class PairIn(BaseModel):
    code:str
    device_id:str
    name:str
    platform:str
    public_key:str=''


def _device_auth(store,request:Request,device_id:str|None=None):
    did=(device_id or request.headers.get('X-NOTSIP-Device-ID','')).strip()
    token=request.headers.get('X-NOTSIP-Device-Token','').strip()
    if not did or not token or not store.device_token_valid(did,token):
        raise HTTPException(401,'device authentication required')
    row=store.row('SELECT status FROM devices WHERE id=?',(did,))
    if not row:raise HTTPException(404,'device not found')
    if str(row.get('status'))=='REVOKED':raise HTTPException(403,'device is revoked')
    return did


def attach(app,require_auth,store,pairing,auth=None):
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in {'/api/pair/code','/api/pair/consume','/api/devices/{device_id}/commands','/api/devices/heartbeat','/api/devices/result'}]
    secret_store=getattr(auth,'secrets',None) if auth is not None else None
    if secret_store is None:raise RuntimeError('pairing hardening requires the canonical secret store')

    @app.get('/api/pair/code')
    async def pair_code(_:None=Depends(require_auth)):
        actor=current_actor();code=store.create_pair_code();secret_store.set('pairing:owner:'+code,{'actor':actor,'created_at':__import__('time').time()});return {'code':code,'actor':actor,'expires_in':300}

    @app.post('/api/pair/consume')
    async def pair_consume(body:PairIn,request:Request,_:None=Depends(require_auth)):
        code=body.code.strip().upper();record=secret_store.get('pairing:owner:'+code)
        actor=current_actor()
        if not isinstance(record,dict) or str(record.get('actor'))!=actor:raise HTTPException(403,'pairing code is not owned by current actor')
        existing_owner=store.device_owner(body.device_id)
        if existing_owner is not None and existing_owner!=actor:
            raise HTTPException(409,'device_id is already owned by another actor')
        if not store.consume_pair_code(code):raise HTTPException(400,'invalid or expired pairing code')
        secret_store.delete('pairing:owner:'+code);token=secrets.token_urlsafe(32);store.pair_device(body.device_id,body.name,body.platform,body.public_key,token,owner=actor)
        return {'status':'PAIRED','device_id':body.device_id,'device_token':token,'actor':actor}

    @app.get('/api/devices/{device_id}/commands')
    async def commands(device_id:str,request:Request):
        did=_device_auth(store,request,device_id)
        return {'commands':store.pull_commands(did)}

    @app.post('/api/devices/heartbeat')
    async def device_heartbeat(device_id:str,token:str):
        row=store.row('SELECT status FROM devices WHERE id=?',(device_id,))
        if not row or not store.device_token_valid(device_id,token):raise HTTPException(401,'invalid device authentication')
        if str(row.get('status'))=='REVOKED':raise HTTPException(403,'device is revoked')
        store.heartbeat(device_id);return {'status':'ONLINE'}

    @app.post('/api/devices/result')
    async def device_result(body:dict,request:Request):
        did=_device_auth(store,request)
        command_id=str(body.get('command_id','')).strip()
        if not command_id:raise HTTPException(400,'command_id is required')
        command=store.row('SELECT device_id,status FROM commands WHERE id=?',(command_id,))
        if not command:raise HTTPException(404,'command not found')
        if str(command.get('device_id'))!=did:raise HTTPException(403,'command does not belong to authenticated device')
        status=str(command.get('status',''))
        if status!='DELIVERED':return {'status':'ALREADY_RECORDED','command_id':command_id,'command_status':status}
        result=body.get('result') or {}
        store.command_result(command_id,str(body.get('status') or 'SUCCESS'),result)
        return {'status':'RECORDED','command_id':command_id,'device_id':did}
