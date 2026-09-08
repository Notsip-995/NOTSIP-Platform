from .execution_gate import ToolExecutionGate


def attach(registry):
    tool=registry.get('email_send')
    if tool is None:return None
    original=tool.fn
    if getattr(tool,'_notsip_guarded',False):
        original=getattr(tool,'_notsip_original_fn',original)
        delattr(tool,'_notsip_guarded')
        if hasattr(tool,'_notsip_original_fn'):delattr(tool,'_notsip_original_fn')
    def send(*args,**kwargs):
        result=original(*args,**kwargs)
        if not isinstance(result,dict):result={'status':'SUCCESS','result':result}
        result=dict(result);result['status']='PARTIAL_SUCCESS';result['verified']=False;result['verification']={'transport':'SMTP server accepted the submission','recipient_delivery_verified':False}
        result['note']='SMTP submission was accepted; NOTSIP has not independently verified recipient delivery.'
        return result
    tool.fn=send
    ToolExecutionGate.wrap_registry(registry)
    return tool
