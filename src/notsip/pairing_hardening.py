from __future__ import annotations
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

def attach(app,require_auth,store,pairing,auth=None):
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in {'/api/pair/code','/api/pair/consume'}]
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
        if not store.consume_pair_code(code):raise HTTPException(400,'invalid or expired pairing code')
        secret_store.delete('pairing:owner:'+code);token=secrets.token_urlsafe(32);store.pair_device(body.device_id,body.name,body.platform,body.public_key,token,owner=actor)
        return {'status':'PAIRED','device_id':body.device_id,'device_token':token,'actor':actor}
