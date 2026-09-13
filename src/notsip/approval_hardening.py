from __future__ import annotations
import time,threading
from fastapi import Depends,HTTPException
from .actor_context import current_actor
_EXECUTION_LOCK=threading.RLock()

def _owned(item,actor):return str((item.get('context') or {}).get('actor') or 'primary-user')==actor

def attach(app, *, require_auth, approvals, registry, audit_log, agent):
    # Every approved tool is protected by the central execution gate. A tool that is
    # not marked _notsip_guarded means an approved tool is not protected by the central execution gate.
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
                approvals.decide(approval_id,False,actor=actor);raise HTTPException(409,'approval expired')
            item=approvals.decide(approval_id,bool(payload.get('approved')),actor=actor)
            if not item or item.get('status')=='PENDING':raise HTTPException(409,'approval state transition failed')
            audit_log.write('approval.decided',approval_id=approval_id,status=item['status'],actor=actor)
            if item['status']=='APPROVED' and payload.get('execute',True):
                result=await agent.run_approved_tool(approval_id)
                if not isinstance(result,dict):result={'status':'SUCCESS','result':result}
                current=approvals._load().get(approval_id) or item
                if result.get('status')=='FAILURE' and current.get('status')=='APPROVED':
                    current['status']='FAILED';current['execution_error']=result.get('error','approval execution failed');current['executed']=time.time();approvals._save({**approvals._load(),approval_id:current})
                audit_log.write('approval.executed',approval_id=approval_id,tool=(current.get('context') or {}).get('tool',''),result=result,actor=actor);item=current
            return item
