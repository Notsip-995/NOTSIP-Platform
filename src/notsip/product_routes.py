from __future__ import annotations
import json,secrets,time
from fastapi import Depends,HTTPException,Request
from fastapi.responses import RedirectResponse
from .updater import UpdateManager
from .policy import Risk
from .tools import Tool
from .execution_gate import ToolExecutionGate
from .oauth_services import OAuthService
from .actor_context import current_actor

_ALLOWED_COMMAND_STATUSES={'SUCCESS','FAILURE','PARTIAL_SUCCESS','UNKNOWN'}
MAX_COMMAND_RESULT_BYTES=1024*1024

def _remove(app,paths):app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in paths]
def _checkpoint_devices(store):return store.rows('SELECT id,name,platform,public_key,token_hash,last_seen,status,data FROM devices')
def _checkpoint_commands(store):return store.rows('SELECT id,device_id,action,payload,status,created,updated,result FROM commands')
def _active_account_key():return 'oidc:active_account:'+current_actor()
def _require_primary():
    if current_actor()!='primary-user':raise HTTPException(403,'primary administrative actor required')

def _device_token_allowed(store,device_id,token):
    placeholder='%s' if getattr(store,'_backend',None) else '?'
    row=store.row(f'SELECT status FROM devices WHERE id={placeholder}',(device_id,))
    if not row or str(row.get('status','')).upper()=='REVOKED':return False
    return bool(token) and store.device_token_valid(device_id,token)

def attach(app,*,require_auth,settings,auth,pairing,nodes,recovery,store,agent,events,accounts,maintenance,DATA,native_voice):
    _remove(app,['/api/oauth/login','/api/oauth/callback','/api/oauth/status','/api/federation/register','/api/federation/{node_id}/heartbeat','/api/federation/challenge','/api/federation/{node_id}/rotate','/api/federation/{node_id}/revoke','/api/recovery/checkpoint','/api/recovery/latest','/api/devices/result','/api/devices/heartbeat','/api/devices/{device_id}/commands'])
    updates=UpdateManager(DATA,settings);oauth_service=OAuthService(auth.secrets,accounts)
    if agent.registry.get('update_apply') is None:agent.registry.add(Tool('update_apply','Apply a downloaded and cryptographically verified NOTSIP executable update.','SELF_MAINTENANCE',Risk.HIGH,{'type':'object','properties':{'path':{'type':'string'}},'required':['path']},lambda path:updates.install_and_verify(__import__('pathlib').Path(path).resolve()),True))
    if agent.registry.get('federation_rotate') is None:agent.registry.add(Tool('federation_rotate','Rotate credentials for an authorized federation node.','CONTROL_SERVER',Risk.HIGH,{'type':'object','properties':{'node_id':{'type':'string'}},'required':['node_id']},nodes.rotate,True))
    if agent.registry.get('federation_revoke') is None:agent.registry.add(Tool('federation_revoke','Revoke an authorized federation node.','CONTROL_SERVER',Risk.HIGH,{'type':'object','properties':{'node_id':{'type':'string'}},'required':['node_id']},nodes.revoke,True))
    if agent.registry.get('recovery_restore') is None:agent.registry.add(Tool('recovery_restore','Restore persistent runtime state from the latest verified checkpoint.','SELF_MAINTENANCE',Risk.HIGH,{'type':'object','properties':{}},lambda:store.restore_runtime_state(recovery.restore_state()['state']),True))
    if agent.registry.get('oauth_revoke') is None:agent.registry.add(Tool('oauth_revoke','Revoke an authorized external OAuth account without weakening other connected accounts.','MANAGE_ACCOUNTS',Risk.HIGH,{'type':'object','properties':{'account_id':{'type':'string'}},'required':['account_id']},lambda account_id:oauth_service.revoke(accounts.get(account_id,{}).get('provider',''),account_id),True))
    ToolExecutionGate.wrap_registry(agent.registry)
    @app.get('/api/recovery/check')
    async def recovery_check(_:None=Depends(require_auth)):
        _require_primary();return recovery.verify_latest()
    @app.get('/api/recovery/state')
    async def recovery_state(_:None=Depends(require_auth)):
        _require_primary();return recovery.restore_state()
    @app.get('/api/federation/challenge')
    async def federation_challenge(node_id:str,nonce:str,_:None=Depends(require_auth)):
        _require_primary()
        if not settings.node_shared_secret:raise HTTPException(503,'federation shared secret is not configured')
        return {'node_id':node_id,'nonce':nonce,'signature':nodes.sign(node_id,nonce),'algorithm':'HMAC-SHA256'}
    @app.post('/api/federation/register')
    async def federation_register(payload:dict,_:None=Depends(require_auth)):
        _require_primary()
        if not settings.node_shared_secret:raise HTTPException(503,'federation shared secret is not configured')
        try:return nodes.register(str(payload['node_id']),str(payload['name']),str(payload.get('platform','unknown')),list(payload.get('capabilities',[])),str(payload.get('public_key','')),str(payload.get('nonce','')),str(payload.get('signature','')),owner='primary-user')
        except PermissionError as exc:raise HTTPException(401,str(exc))
    @app.post('/api/federation/{node_id}/heartbeat')
    async def federation_heartbeat(node_id:str,payload:dict):
        if not settings.node_shared_secret:raise HTTPException(503,'federation shared secret is not configured')
        try:return {'status':'SUCCESS','lease':nodes.heartbeat(node_id,str(payload.get('token','')),list(payload.get('capabilities',[])),payload.get('health') or {},str(payload.get('nonce','')),str(payload.get('signature','')))}
        except PermissionError as exc:raise HTTPException(401,str(exc))
    @app.post('/api/federation/{node_id}/rotate')
    async def federation_rotate(node_id:str,_:None=Depends(require_auth)):
        _require_primary();return await agent.run_tool('federation_rotate',{'node_id':node_id})
    @app.post('/api/federation/{node_id}/revoke')
    async def federation_revoke(node_id:str,_:None=Depends(require_auth)):
        _require_primary();return await agent.run_tool('federation_revoke',{'node_id':node_id})
    @app.post('/api/recovery/checkpoint')
    async def checkpoint(_:None=Depends(require_auth)):
        _require_primary();state={'tasks':store.tasks(),'devices':_checkpoint_devices(store),'commands':_checkpoint_commands(store),'world':getattr(agent,'world',None).snapshot() if getattr(agent,'world',None) else {},'timestamp':time.time()};return {'status':'SUCCESS','path':recovery.checkpoint(state)}
    @app.get('/api/recovery/latest')
    async def latest_checkpoint(_:None=Depends(require_auth)):
        _require_primary();return {'checkpoint':recovery.latest(),'verified':recovery.verify_latest()}
    @app.post('/api/recovery/restore')
    async def restore(_:None=Depends(require_auth)):
        _require_primary();result=await agent.run_tool('recovery_restore',{});return {'status':result.get('status','SUCCESS'),'result':result,'restart_required':result.get('status') in {'SUCCESS','PARTIAL_SUCCESS'},'action':'restart_runtime_to_rebuild_in_memory_state'}
    @app.get('/api/update/check')
    async def update_check(_:None=Depends(require_auth)):
        return await updates.check()
    @app.post('/api/update/download')
    async def update_download(payload:dict,_:None=Depends(require_auth)):
        _require_primary()
        if not settings.github_update_enabled:raise HTTPException(403,'automatic updates disabled')
        asset_name=str(payload.get('asset_name') or 'NOTSIP.exe').strip()
        if '/' in asset_name or '\\' in asset_name or asset_name != __import__('pathlib').Path(asset_name).name:raise HTTPException(400,'invalid update asset name')
        supplied=str(payload.get('sha256','')).strip().lower()
        try:result=await updates.download_release_asset(asset_name)
        except ValueError as exc:raise HTTPException(400,str(exc))
        if supplied and supplied!=str(result.get('sha256','')).lower():
            try:__import__('pathlib').Path(result['path']).unlink(missing_ok=True)
            except Exception:pass
            raise HTTPException(400,'supplied SHA-256 does not match the trusted release manifest')
        return result
    @app.post('/api/update/apply')
    async def update_apply(payload:dict,_:None=Depends(require_auth)):
        _require_primary()
        if not settings.github_update_enabled:raise HTTPException(403,'automatic updates disabled')
        candidate=__import__('pathlib').Path(str(payload.get('path',''))).resolve();update_dir=updates.dir.resolve()
        if update_dir not in candidate.parents or candidate.suffix.lower()!='.exe' or not candidate.is_file():raise HTTPException(400,'update path must point to a downloaded EXE inside NOTSIP updates directory')
        return await agent.run_tool('update_apply',{'path':str(candidate)})
    @app.get('/api/oauth/status')
    async def oauth_status(_:None=Depends(require_auth)):return {'mode':auth.mode,'provider':settings.oidc_provider,'configured':auth.oidc.configured,'issuer':auth.oidc.issuer,'client_id_configured':bool(auth.oidc.client_id),'accounts':accounts.list()}
    @app.get('/api/oauth/login')
    async def oauth_login():
        if not auth.oidc.configured:raise HTTPException(503,'OIDC is not configured')
        verifier,challenge=__import__('notsip.security',fromlist=['pkce_pair']).pkce_pair();state=secrets.token_urlsafe(32);nonce=secrets.token_urlsafe(24);auth.sessions['oidc:'+state]={'verifier':verifier,'nonce':nonce,'expires':time.time()+600,'actor':current_actor()};return RedirectResponse(await auth.oidc.authorize_url(state,challenge,nonce))
    @app.get('/api/oauth/callback')
    async def oauth_callback(code:str,state:str):
        pending=auth.sessions.pop('oidc:'+state,None)
        if not pending or pending.get('expires',0)<time.time():raise HTTPException(400,'invalid or expired OIDC state')
        tokens=await auth.oidc.exchange(code,pending['verifier']);claims={}
        if tokens.get('id_token'):claims=await auth.oidc.validate_id_token(tokens['id_token'],pending['nonce'])
        elif tokens.get('access_token'):claims=await auth.oidc.userinfo(tokens['access_token'])
        actor=str(pending.get('actor') or 'primary-user');account=accounts.upsert(settings.oidc_provider,claims.get('sub','user'),claims.get('email',''),auth.oidc.scopes,{'expires_at':tokens.get('expires_at'),'token_type':tokens.get('token_type')},owner=actor);accounts.save_tokens(account['id'],tokens,owner=actor);auth.secrets.set('oidc:active_account:'+actor,account['id'])
        session=auth.mint_session({'claims':claims,'account_id':account['id']});r=RedirectResponse('/');r.set_cookie('notsip_session',session,httponly=True,secure=settings.oidc_redirect_uri.startswith('https://'),samesite='lax',max_age=settings.session_ttl);return r
    @app.post('/api/oauth/revoke')
    async def oauth_revoke(payload:dict,_:None=Depends(require_auth)):
        account_id=str(payload.get('account_id') or auth.secrets.get(_active_account_key(),''));item=accounts.get(account_id) if account_id else None
        if not item:raise HTTPException(404,'OAuth account not found')
        return await agent.run_tool('oauth_revoke',{'account_id':account_id})
    @app.post('/api/devices/result')
    async def device_result(payload:dict,request:Request):
        device_id=request.headers.get('X-NOTSIP-Device-ID','');device_token=request.headers.get('X-NOTSIP-Device-Token','')
        if not _device_token_allowed(store,device_id,device_token):raise HTTPException(401,'device authentication required')
        command_id=str(payload.get('command_id',''));placeholder='%s' if getattr(store,'_backend',None) else '?';command=store.row(f'SELECT device_id FROM commands WHERE id={placeholder}',(command_id,))
        if not command or command['device_id']!=device_id:raise HTTPException(403,'command does not belong to authenticated device')
        status=str(payload.get('status','UNKNOWN')).upper()
        if status not in _ALLOWED_COMMAND_STATUSES:raise HTTPException(400,'invalid command result status')
        result_payload=payload.get('result') or {}
        if not isinstance(result_payload,dict):raise HTTPException(400,'command result must be an object')
        if len(json.dumps(result_payload,separators=(',',':'),default=str).encode('utf-8'))>MAX_COMMAND_RESULT_BYTES:raise HTTPException(413,'command result exceeds maximum size')
        ok=store.command_result(command_id,status,result_payload,device_id)
        if not ok:raise HTTPException(409,'command result was not recorded for authenticated device')
        return {'status':'RECORDED','device_id':device_id,'command_id':command_id}
    @app.post('/api/devices/heartbeat')
    async def device_heartbeat(request:Request):
        device_id=request.headers.get('X-NOTSIP-Device-ID','');token=request.headers.get('X-NOTSIP-Device-Token','')
        if not _device_token_allowed(store,device_id,token):raise HTTPException(401,'device authentication required')
        store.heartbeat(device_id);return {'status':'ONLINE','device_id':device_id}
    @app.get('/api/devices/{device_id}/commands')
    async def device_commands(device_id:str,x_notsip_device_token:str=__import__('fastapi').Header('',alias='X-NOTSIP-Device-Token')):
        if not _device_token_allowed(store,device_id,x_notsip_device_token):raise HTTPException(401,'Invalid device token')
        return {'commands':store.pull_commands(device_id)}
