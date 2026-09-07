from __future__ import annotations
import asyncio, hashlib, json, os, secrets, time
from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from .updater import UpdateManager
from .events import Event

def _remove(app, paths):
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in paths]

def attach(app, *, require_auth, settings, auth, pairing, nodes, recovery, store, agent, events, accounts, maintenance, DATA, native_voice):
    _remove(app, ['/api/oauth/login','/api/oauth/callback','/api/oauth/status','/api/federation/register','/api/federation/{node_id}/heartbeat','/api/federation/challenge','/api/federation/{node_id}/rotate','/api/federation/{node_id}/revoke','/api/recovery/checkpoint','/api/recovery/latest'])
    updates=UpdateManager(DATA,settings)
    @app.get('/api/recovery/check')
    async def recovery_check(_:None=Depends(require_auth)):return recovery.verify_latest()
    @app.get('/api/recovery/state')
    async def recovery_state(_:None=Depends(require_auth)):return recovery.restore_state()
    @app.get('/api/federation/challenge')
    async def federation_challenge(node_id:str,nonce:str,_:None=Depends(require_auth)):
        return {'node_id':node_id,'nonce':nonce,'signature':nodes.sign(node_id,nonce),'algorithm':'HMAC-SHA256'}
    @app.post('/api/federation/register')
    async def federation_register(payload:dict,_:None=Depends(require_auth)):
        return nodes.register(str(payload['node_id']),str(payload['name']),str(payload.get('platform','unknown')),list(payload.get('capabilities',[])),str(payload.get('public_key','')),str(payload.get('nonce','')),str(payload.get('signature','')))
    @app.post('/api/federation/{node_id}/heartbeat')
    async def federation_heartbeat(node_id:str,payload:dict):
        return {'status':'SUCCESS','lease':nodes.heartbeat(node_id,str(payload.get('token','')),list(payload.get('capabilities',[])),payload.get('health') or {},str(payload.get('nonce','')),str(payload.get('signature','')))}
    @app.post('/api/federation/{node_id}/rotate')
    async def federation_rotate(node_id:str,_:None=Depends(require_auth)):return nodes.rotate(node_id)
    @app.post('/api/federation/{node_id}/revoke')
    async def federation_revoke(node_id:str,_:None=Depends(require_auth)):return nodes.revoke(node_id)
    @app.post('/api/recovery/checkpoint')
    async def checkpoint(_:None=Depends(require_auth)):
        return {'status':'SUCCESS','path':recovery.checkpoint({'tasks':store.tasks(),'devices':store.devices(),'world':getattr(agent,'world',None).snapshot() if getattr(agent,'world',None) else {},'timestamp':time.time()})}
    @app.get('/api/recovery/latest')
    async def latest_checkpoint(_:None=Depends(require_auth)):return {'checkpoint':recovery.latest(),'verified':recovery.verify_latest()}
    @app.post('/api/recovery/restore')
    async def restore(_:None=Depends(require_auth)):
        state=recovery.restore_state()['state'];result=store.restore_runtime_state(state);return {'status':'RESTORED','result':result,'restart_required':True,'action':'restart_runtime_to_rebuild_in_memory_state'}
    @app.get('/api/update/check')
    async def update_check(_:None=Depends(require_auth)):return await updates.check()
    @app.post('/api/update/download')
    async def update_download(payload:dict,_:None=Depends(require_auth)):
        if not settings.github_update_enabled:raise HTTPException(403,'automatic updates disabled')
        asset_url=str(payload.get('asset_url',''));expected_repo=f"https://github.com/{settings.github_repository}/releases/"
        if not asset_url.startswith(expected_repo):raise HTTPException(400,'update asset must originate from configured GitHub repository')
        expected_sha=str(payload.get('sha256','')).strip()
        if len(expected_sha)!=64:raise HTTPException(400,'update SHA-256 is required')
        return await updates.download(asset_url,expected_sha)
    @app.post('/api/update/apply')
    async def update_apply(payload:dict,_:None=Depends(require_auth)):
        if not settings.github_update_enabled:raise HTTPException(403,'automatic updates disabled')
        result=updates.install_and_verify(__import__('pathlib').Path(str(payload['path'])).resolve())
        async def stop_after_response():
            await asyncio.sleep(1.0)
            os._exit(0)
        asyncio.create_task(stop_after_response())
        return result
    @app.get('/api/oauth/status')
    async def oauth_status(_:None=Depends(require_auth)):return {'mode':auth.mode,'provider':settings.oidc_provider,'configured':auth.oidc.configured,'issuer':auth.oidc.issuer,'client_id_configured':bool(auth.oidc.client_id),'accounts':accounts.list()}
    @app.get('/api/oauth/login')
    async def oauth_login():
        if not auth.oidc.configured:raise HTTPException(503,'OIDC is not configured')
        verifier,challenge=__import__('notsip.security',fromlist=['pkce_pair']).pkce_pair();state=secrets.token_urlsafe(32);nonce=secrets.token_urlsafe(24);auth.sessions['oidc:'+state]={'verifier':verifier,'nonce':nonce,'expires':time.time()+600};return RedirectResponse(await auth.oidc.authorize_url(state,challenge,nonce))
    @app.get('/api/oauth/callback')
    async def oauth_callback(code:str,state:str):
        pending=auth.sessions.pop('oidc:'+state,None)
        if not pending or pending.get('expires',0)<time.time():raise HTTPException(400,'invalid or expired OIDC state')
        tokens=await auth.oidc.exchange(code,pending['verifier']);claims={}
        if tokens.get('id_token'):claims=await auth.oidc.validate_id_token(tokens['id_token'],pending['nonce'])
        elif tokens.get('access_token'):claims=await auth.oidc.userinfo(tokens['access_token'])
        account=accounts.upsert(settings.oidc_provider,claims.get('sub','user'),claims.get('email',''),auth.oidc.scopes,{'expires_at':tokens.get('expires_at'),'token_type':tokens.get('token_type')});accounts.save_tokens(account['id'],tokens);auth.secrets.set('oidc:active_account',account['id'])
        session=auth.mint_session({'claims':claims,'account_id':account['id']});r=RedirectResponse('/');r.set_cookie('notsip_session',session,httponly=True,secure=settings.oidc_redirect_uri.startswith('https://'),samesite='lax',max_age=settings.session_ttl);return r
    @app.post('/api/oauth/revoke')
    async def oauth_revoke(payload:dict,_:None=Depends(require_auth)):
        account_id=str(payload.get('account_id') or auth.secrets.get('oidc:active_account',''));item=accounts.get(account_id) if account_id else None
        if not item:raise HTTPException(404,'OAuth account not found')
        tokens=accounts.tokens(account_id);provider=item.get('provider','');url={'google':'https://oauth2.googleapis.com/revoke'}.get(provider)
        if url and tokens.get('access_token'):
            import httpx
            try:
                async with httpx.AsyncClient(timeout=15) as c:r=await c.post(url,data={'token':tokens['access_token']});r.raise_for_status()
            except Exception as exc:raise HTTPException(502,f'provider revocation failed: {exc}')
        accounts.disconnect(account_id)
        if auth.secrets.get('oidc:active_account','')==account_id:auth.secrets.set('oidc:active_account','')
        return {'status':'SUCCESS','revoked':True,'account_id':account_id,'provider_revoked':bool(url and tokens.get('access_token'))}
