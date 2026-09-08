import asyncio
from notsip.actor_context import set_actor,reset_actor
from notsip.pairing_hardening import attach,PairIn

class Pairing:
    def __init__(self):self.used=[]
    def consume_code(self,code):self.used.append(code);return code=='VALID'

class Store:
    def __init__(self):self.calls=[]
    def pair_device(self,*args,**kwargs):self.calls.append((args,kwargs))

class App:
    def __init__(self):self.fn=None
    @property
    def router(self):return type('R',(),{'routes':[]})()
    def post(self,path):
        def deco(fn):self.fn=fn;return fn
        return deco


def test_pairing_records_current_actor():
    app=App();pairing=Pairing();store=Store();attach(app,lambda:None,store,pairing)
    token=set_actor('issuer:user-a')
    try:
        result=asyncio.run(app.fn(PairIn(code='VALID',device_id='phone-a',name='A',platform='android'),None,None))
    finally:reset_actor(token)
    assert result['status']=='PAIRED' and result['actor']=='issuer:user-a'
    assert store.calls[0][1]['owner']=='issuer:user-a'
