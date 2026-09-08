from __future__ import annotations
import json,time
from collections import Counter
from fastapi import Depends,HTTPException
from .actor_context import current_actor

_PUBLIC_SOURCES={'public','brave','system','health-analytics','predictive-maintenance','runtime','scheduler','federation'}

def _payload(value):
    if isinstance(value,dict):return value
    if isinstance(value,str):
        try:return json.loads(value)
        except Exception:return {}
    return {}

def _allowed_event(event,actor):
    if actor=='primary-user':return True
    payload=_payload(event.get('payload'))
    event_actor=str(payload.get('actor') or payload.get('owner') or '').strip()
    if event_actor:return event_actor==actor
    return str(event.get('source') or '').lower() in _PUBLIC_SOURCES

class EventReconstructor:
    def __init__(self,store,journal=None):self.store,self.journal=store,journal
    def reconstruct(self,since=None,until=None,limit=500,actor=None):
        actor=actor or current_actor();lo=float(since) if since is not None else 0;hi=float(until) if until is not None else float('inf');events=[]
        if self.journal:
            for e in self.journal.recent(max(1,min(int(limit),5000))):
                if not _allowed_event(e,actor):continue
                ts=float(e.get('ts') or 0)
                if lo<=ts<=hi:events.append({'ts':ts,'type':e.get('type'),'source':e.get('source'),'payload':e.get('payload'),'timestamp':e.get('timestamp')})
        for r in self.store.audit_recent(max(1,min(int(limit),2000))):
            if actor!='primary-user' and str(r.get('user_id') or 'primary-user')!=actor:continue
            ts=float(r.get('ts') or 0)
            if lo<=ts<=hi:events.append({'ts':ts,'type':'audit','source':'audit','payload':{'tool':r.get('tool'),'action':r.get('action'),'request':r.get('request'),'result':r.get('result'),'user_id':r.get('user_id')}})
        events.sort(key=lambda x:x['ts']);gaps=[]
        for a,b in zip(events,events[1:]):
            delta=b['ts']-a['ts']
            if delta>300:gaps.append({'from':a['ts'],'to':b['ts'],'seconds':delta,'impact':'timeline may be incomplete'})
        counts=dict(Counter(e.get('type') or 'unknown' for e in events));coverage=min(1.0,len(events)/20);gap_penalty=min(.5,len(gaps)*.1);confidence=max(.1,min(.95,.25+.65*coverage-gap_penalty)) if events else .1
        hypotheses=[]
        if gaps:hypotheses.append({'type':'missing_observations','confidence':min(.8,.4+.1*len(gaps)),'evidence':gaps})
        if counts.get('audit',0) and any(k in counts for k in ('perception.observed','health.warning','maintenance.prediction')):hypotheses.append({'type':'mixed_operational_and_observation_timeline','confidence':.7,'evidence_types':sorted(counts)})
        return {'status':'SUCCESS','generated_at':time.time(),'actor':actor,'window':{'since':lo,'until':None if hi==float('inf') else hi},'events':events[-max(1,min(int(limit),5000)):],'counts':counts,'gaps':gaps,'hypotheses':hypotheses,'confidence':confidence,'confidence_explanation':'confidence estimates event coverage and penalizes detected timeline gaps; it is not causal proof'}

def attach(app,require_auth,store,journal=None):
    recon=EventReconstructor(store,journal)
    @app.get('/api/events/reconstruct')
    async def reconstruct(since:float|None=None,until:float|None=None,limit:int=500,_:None=Depends(require_auth)):
        if since is not None and until is not None and until<since:raise HTTPException(400,'until must be >= since')
        return recon.reconstruct(since,until,limit,current_actor())
    @app.get('/api/events/recent')
    async def recent_events(limit:int=200,_:None=Depends(require_auth)):
        actor=current_actor();rows=journal.recent(limit) if journal else [];return {'events':[r for r in rows if _allowed_event(r,actor)]}
