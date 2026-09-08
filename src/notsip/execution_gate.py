from __future__ import annotations
import json,threading,time
from functools import wraps
from .actor_context import current_actor

class ToolExecutionGate:
    """Central guard used by Tool.fn so every invocation observes policy and actor-bound approval state."""
    _policy=None;_approvals=None;_lock=threading.RLock()
    @classmethod
    def configure(cls,policy,approvals):cls._policy=policy;cls._approvals=approvals
    @classmethod
    def _approved(cls,name,args):
        approvals=cls._approvals
        if approvals is None:return False
        actor=current_actor()
        with cls._lock:
            try:
                data=approvals._load();now=time.time();canonical=json.dumps(args,sort_keys=True,separators=(',',':'),default=str);candidates=[]
                for item in data.values():
                    if item.get('status')!='APPROVED' or float(item.get('decided',0))+60<now:continue
                    context=item.get('context') or {}
                    if context.get('tool')!=name or context.get('actor','primary-user')!=actor:continue
                    expected=json.dumps(context.get('args') or {},sort_keys=True,separators=(',',':'),default=str)
                    if expected==canonical:candidates.append(item)
                if not candidates:return False
                item=min(candidates,key=lambda x:float(x.get('decided',0)));item['status']='EXECUTING';item['execution_claimed']=now;approvals._save(data);return item['id']
            except Exception:return False
    @classmethod
    def wrap_registry(cls,registry):
        for tool in registry.all():
            if getattr(tool,'_notsip_guarded',False):continue
            original=tool.fn
            @wraps(original)
            def guarded(*args,__tool=tool,__original=original,**kwargs):
                approved=bool(kwargs.pop('_notsip_approved',False));grant=True if approved else cls._approved(__tool.name,args[0] if len(args)==1 and isinstance(args[0],dict) else kwargs);policy=cls._policy
                if policy is None:raise RuntimeError('NOTSIP tool policy gate is not configured')
                d=policy.decide(__tool.risk,__tool.destructive,__tool.capability,approved=bool(grant))
                if not d.allowed:
                    if grant and grant is not True:cls._release_approval(grant,d.reason)
                    raise PermissionError(d.reason)
                try:result=__original(*args,**kwargs)
                except Exception as exc:
                    if grant and grant is not True:cls._finish_approval(grant,'FAILED',str(exc),None)
                    raise
                if grant and grant is not True:
                    status=result.get('status') if isinstance(result,dict) else 'SUCCESS';outcome={'SUCCESS':'EXECUTED','FAILURE':'FAILED','UNKNOWN':'UNKNOWN','PARTIAL_SUCCESS':'PARTIAL_SUCCESS'}.get(str(status).upper(),'EXECUTED');cls._finish_approval(grant,outcome,'' if outcome=='EXECUTED' else str(result.get('error','')) if isinstance(result,dict) else '')
                return result
            tool.fn=guarded;tool._notsip_original_fn=original;tool._notsip_guarded=True
    @classmethod
    def _release_approval(cls,approval_id,reason):
        approvals=cls._approvals
        if approvals is None:return
        with cls._lock:
            try:
                data=approvals._load();item=data.get(approval_id)
                if item and item.get('status')=='EXECUTING':item['status']='APPROVED';item['execution_claimed']=None;item['execution_blocked']=reason;approvals._save(data)
            except Exception:return
    @classmethod
    def _finish_approval(cls,approval_id,status,error=''):
        approvals=cls._approvals
        if approvals is None:return
        with cls._lock:
            try:
                data=approvals._load();item=data.get(approval_id)
                if item and item.get('status')=='EXECUTING':
                    item['status']=status;item['executed']=time.time()
                    if error:item['execution_error']=error
                    approvals._save(data)
            except Exception:return
