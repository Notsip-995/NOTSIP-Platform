from __future__ import annotations
import time
from collections import Counter
from fastapi import Depends, HTTPException

class EventReconstructor:
    def __init__(self,store): self.store=store
    def reconstruct(self, since=None, until=None, limit=500):
        rows=self.store.audit_recent(max(1,min(int(limit),2000)))
        lo=float(since) if since is not None else 0
        hi=float(until) if until is not None else float('inf')
        events=[]
        for r in rows:
            ts=float(r.get('ts') or 0)
            if lo<=ts<=hi: events.append({'ts':ts,'tool':r.get('tool'),'action':r.get('action'),'request':r.get('request'),'result':r.get('result'),'user_id':r.get('user_id')})
        events.sort(key=lambda x:x['ts'])
        gaps=[]
        for a,b in zip(events,events[1:]):
            delta=b['ts']-a['ts']
            if delta>300:gaps.append({'from':a['ts'],'to':b['ts'],'seconds':delta})
        return {'status':'SUCCESS','generated_at':time.time(),'window':{'since':lo,'until':None if hi==float('inf') else hi},'events':events,'counts':dict(Counter(e.get('action') or 'unknown' for e in events)),'gaps':gaps,'confidence':0.85 if events else 0.25}

def attach(app,require_auth,store):
    recon=EventReconstructor(store)
    @app.get('/api/events/reconstruct')
    async def reconstruct(since:float|None=None,until:float|None=None,limit:int=500,_:None=Depends(require_auth)):
        if since is not None and until is not None and until<since: raise HTTPException(400,'until must be >= since')
        return recon.reconstruct(since,until,limit)
