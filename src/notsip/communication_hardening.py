from __future__ import annotations


def attach(registry):
    tool=registry.get('email_send')
    if tool is None:return None
    original=tool.fn
    def send(*args,**kwargs):
        result=original(*args,**kwargs)
        if not isinstance(result,dict):result={'status':'SUCCESS','result':result}
        result=dict(result);result['status']='PARTIAL_SUCCESS';result['verified']=False;result['verification']={'transport':'SMTP server accepted the submission','recipient_delivery_verified':False}
        result['note']='SMTP submission was accepted; NOTSIP has not independently verified recipient delivery.'
        return result
    tool.fn=send
    return tool
