from __future__ import annotations
import json,time
from collections import Counter
from pathlib import Path
from fastapi import Depends, HTTPException

class EventReconstructor:
    def __init__(self,store,journal=None): self.store,self.journal=store,journal
    def reconstruct(self,since=None,until=None,limit=500):
        lo=float(since) if since is not None else 0;hi=float(until) if until is not None else float('inf');events=[]
        if self.journal:
            for e in self.journal.recent(max(1,min(int(limit),5000))):
                ts=float(e.get('ts') or 0)
                if lo<=ts<=hi:events.append({'ts':ts,'type':e.get('type'),'source':e.get('source'),'payload':e.get('payload'),'timestamp':e.get('timestamp')})
        for r in self.store.audit_recent(max(1,min(int(limit),2000))):
            ts=float(r.get('ts') or 0)
            if lo<=ts<=hi:events.append({'ts':ts,'type':'audit','source':'audit','payload':{'tool':r.get('tool'),'action':r.get('action'),'request':r.get('request'),'result':r.get('result'),'user_id':r.get('user_id')}})
        events.sort(key=lambda x:x['ts']);gaps=[]
        for a,b in zip(events,events[1:]):
            delta=b['ts']-a['ts']
            if delta>300:gaps.append({'from':a['ts'],'to':b['ts'],'seconds':delta})
        return {'status':'SUCCESS','generated_at':time.time(),'window':{'since':lo,'until':None if hi==float('inf') else hi},'events':events[-max(1,min(int(limit),5000)):],'counts':dict(Counter(e.get('type') or 'unknown' for e in events)),'gaps':gaps,'confidence':0.9 if events else 0.25}

def attach(app,require_auth,store,journal=None):
    recon=EventReconstructor(store,journal)
    @app.get('/api/events/reconstruct')
    async def reconstruct(since:float|None=None,until:float|None=None,limit:int=500,_:None=Depends(require_auth)):
        if since is not None and until is not None and until<since:raise HTTPException(400,'until must be >= since')
        return recon.reconstruct(since,until,limit)
    @app.get('/api/events/recent')
    async def recent_events(limit:int=200,_:None=Depends(require_auth)):
        return {'events':journal.recent(limit) if journal else []}
