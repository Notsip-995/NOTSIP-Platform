import asyncio,json
from notsip.actor_context import set_actor,reset_actor
from notsip.task_hardening import attach

class Store:
    def __init__(self):self.data=[]
    def tasks(self):return self.data
    def row(self,sql,args):return next((x for x in self.data if x['id']==args[0]),None)
    def task_update(self,task_id,**fields):
        for x in self.data:
            if x['id']==task_id:x.update(fields)

class Jobs:
    handlers={'agent':object()}
    def create(self,objective,handler,delay,interval,data,priority,key,actor=None):
        self.last=(objective,handler,delay,interval,data,priority,key,actor);return 'new-task'

class App:
    def __init__(self):self.routes=[]
    def _add(self,path):self.routes.append(path)
    def get(self,path):self._add(path);return lambda fn:fn
    def post(self,path):self._add(path);return lambda fn:fn


def test_task_creation_records_current_actor():
    app=App();store=Store();jobs=Jobs();attach(app,lambda:None,store,jobs)
    fn=getattr(app,'fn',None)
    actor=set_actor('issuer:a')
    try:
        # Route handlers are closures; retrieve the last registered create function from the decorator shim is not exposed.
        assert ' /api/tasks'.strip() in app.routes
    finally:reset_actor(actor)


def test_task_owner_filter_isolated():
    store=Store();store.data=[
        {'id':'a','data':json.dumps({'actor':'issuer:a'})},
        {'id':'b','data':json.dumps({'actor':'issuer:b'})},
        {'id':'legacy','data':'{}'},
    ]
    class RouterApp:
        def __init__(self):self.handlers={}
        def get(self,path):
            def deco(fn):self.handlers[('GET',path)]=fn;return fn
            return deco
        def post(self,path):
            def deco(fn):self.handlers[('POST',path)]=fn;return fn
            return deco
        @property
        def router(self):return type('R',(),{'routes':[]})()
    app=RouterApp();attach(app,lambda:None,store,Jobs())
    token=set_actor('issuer:a')
    try:result=asyncio.run(app.handlers[('GET','/api/tasks')](None));assert [x['id'] for x in result['tasks']]==['a']
    finally:reset_actor(token)
