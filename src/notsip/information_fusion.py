from __future__ import annotations
import time
from fastapi import Depends, HTTPException

class InformationFusion:
    def __init__(self, store, web): self.store,self.web=store,web
    def stored(self, query, limit=50):
        q=str(query).lower();facts=self.store.facts(limit)
        return [f for f in facts if q in str(f.get('statement','')).lower() or q in str(f.get('url','')).lower()]
    async def fuse(self, query, count=5):
        local=self.stored(query)
        remote=[]
        if self.web.enabled:
            remote=await self.web.search(query,max(1,min(int(count),20)))
            for item in remote:
                self.store.fact(item.get('title',''), 'brave', item.get('url',''), .55, {'query':query,'retrieved_at':time.time()})
        evidence=[]
        for f in local: evidence.append({'kind':'stored_fact','statement':f.get('statement',''),'source':f.get('source',''),'url':f.get('url',''),'confidence':f.get('confidence',0.0),'retrieved':f.get('retrieved')})
        for r in remote: evidence.append({'kind':'web','statement':r.get('title',''),'source':'brave','url':r.get('url',''),'confidence':.55,'description':r.get('description',''),'retrieved':time.time()})
        return {'query':query,'evidence':evidence,'counts':{'stored':len(local),'web':len(remote)},'generated_at':time.time()}

def attach(app, require_auth, store, web):
    service=InformationFusion(store,web)
    @app.get('/api/information/fuse')
    async def information_fuse(q:str,count:int=5,_:None=Depends(require_auth)):
        q=q.strip()
        if not q: raise HTTPException(400,'query is required')
        return await service.fuse(q,count)
    @app.get('/api/information/stored')
    async def information_stored(q:str,limit:int=50,_:None=Depends(require_auth)):
        return {'query':q,'evidence':service.stored(q,max(1,min(int(limit),200)))}
