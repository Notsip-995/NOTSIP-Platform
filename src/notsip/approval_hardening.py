from __future__ import annotations
import time,threading
from fastapi import Depends,HTTPException
from .actor_context import current_actor
_EXECUTION_LOCK=threading.RLock()

def _owned(item,actor):return str((item.get('context') or {}).get('actor') or 'primary-user')==actor

def attach(app, *, require_auth, approvals, registry, audit_log, agent):
    paths={'/api/approvals','/api/approvals/{approval_id}'}
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in paths]
    @app.get('/api/approvals')
    async def list_approvals(_:None=Depends(require_auth)):
        actor=current_actor();return {'pending':[x for x in approvals.pending() if _owned(x,actor)]}
    @app.post('/api/approvals')
    async def create_approval(payload:dict,_:None=Depends(require_auth)):
        actor=current_actor();context=dict(payload.get('context') or {});context['actor']=actor
        return approvals.request(str(payload.get('action','')),str(payload.get('reason','')),context)
    @app.post('/api/approvals/{approval_id}')
    async def decide_approval(approval_id:str,payload:dict,_:None=Depends(require_auth)):
        actor=current_actor()
        with _EXECUTION_LOCK:
            current=approvals._load().get(approval_id)
            if not current or not _owned(current,actor):raise HTTPException(404,'approval not found')
            if current.get('status')!='PENDING':raise HTTPException(409,f"approval already {current.get('status','resolved')}")
            if float(current.get('expires',0))<=time.time():
                approvals.decide(approval_id,False);raise HTTPException(409,'approval expired')
            item=approvals.decide(approval_id,bool(payload.get('approved')))
            if not item or item.get('status')=='PENDING':raise HTTPException(409,'approval state transition failed')
            audit_log.write('approval.decided',approval_id=approval_id,status=item['status'],actor=actor)
            if item['status']=='APPROVED' and payload.get('execute',True):
                ctx=item.get('context') or {};name=str(ctx.get('tool',''));args=ctx.get('args') or {};tool=registry.get(name)
                if not tool:raise HTTPException(400,'approved tool no longer exists')
                if str(ctx.get('actor') or 'primary-user')!=actor:raise HTTPException(403,'approval actor mismatch')
                try:
                    result=tool.fn(**args);result=await result if hasattr(result,'__await__') else result
                except Exception as exc:
                    audit_log.write('approval.execution_failed',approval_id=approval_id,tool=name,error=str(exc),actor=actor);raise
                result=result if isinstance(result,dict) else {'status':'SUCCESS','result':result}
                current=approvals._load().get(approval_id) or item;current['execution']=result;current['executed']=time.time();current['status']=result.get('status','SUCCESS') if result.get('status') in {'FAILED','PARTIAL_SUCCESS','UNKNOWN'} else 'EXECUTED';approvals._save({**approvals._load(),approval_id:current});audit_log.write('approval.executed',approval_id=approval_id,tool=name,result=result,actor=actor);item=current
            return item
