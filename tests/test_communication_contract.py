

def test_email_send_contract_does_not_claim_recipient_delivery():
    from notsip.communication_hardening import attach
    class Tool:
        def __init__(self): self.fn=lambda **kwargs:{'status':'SUCCESS','to':'example'}
    class Registry:
        def __init__(self): self.tool=Tool()
        def get(self,name): return self.tool if name=='email_send' else None
    registry=Registry();attach(registry);result=registry.tool.fn()
    assert result['status']=='PARTIAL_SUCCESS'
    assert result['verified'] is False
    assert result['verification']['recipient_delivery_verified'] is False
