from __future__ import annotations
import importlib,secrets
from fastapi import Depends,HTTPException,Request
from pydantic import BaseModel
from .actor_context import current_actor

class PairIn(BaseModel):
    code:str
    device_id:str
    name:str
    platform:str
    public_key:str=''

def attach(app,require_auth,store,pairing):
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None)!='/api/pair/consume']
    @app.post('/api/pair/consume')
    async def pair_consume(body:PairIn,request:Request,_:None=Depends(require_auth)):
        if not pairing.consume_code(body.code):raise HTTPException(400,'invalid or expired pairing code')
        token=secrets.token_urlsafe(32);store.pair_device(body.device_id,body.name,body.platform,body.public_key,token,owner=current_actor())
        return {'status':'PAIRED','device_id':body.device_id,'device_token':token,'actor':current_actor()}
