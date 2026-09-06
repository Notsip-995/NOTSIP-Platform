from __future__ import annotations
import json, asyncio, hashlib, secrets
from pathlib import Path
from fastapi import FastAPI,Request,HTTPException,Depends,Header,WebSocket,WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel
from .config import settings
from .store import Store
from .policy import Policy,Risk
from .events import Event,EventBus
from .provider import OpenAICompatible
from .tools import Registry,Tool,calc,list_workspace,read_workspace,windows_exec,diagnostics
from .integrations import Brave,Webhook
from .world import WorldModel
from .jobs import JobRunner
from .agent import Agent
settings.ensure(); workspace=str(Path(settings.data_dir)/'workspace'); store=Store(settings.data_dir); policy=Policy(settings.autonomy_level); registry=Registry(); events=EventBus(); provider=OpenAICompatible(settings.llm_base_url,settings.llm_api_key,settings.llm_model); world=WorldModel(store); jobs=JobRunner(store,events); pairing=__import__('notsip.android_bridge',fromlist=['Pairing']).Pairing(store); brave=Brave(settings.brave_api_key); webhook=Webhook(settings.event_hmac_secret)
registry.add(Tool('calculator','Calculate safe arithmetic.','COMPUTE',Risk.LOW,{'type':'object','properties':{'expr':{'type':'string'}},'required':['expr']},calc))
registry.add(Tool('list_files','List files in NOTSIP workspace.','READ_FILES',Risk.LOW,{'type':'object','properties':{'query':{'type':'string'}}},lambda query='':list_workspace(workspace,query)))
registry.add(Tool('read_file','Read a text file in NOTSIP workspace.','READ_FILES',Risk.LOW,{'type':'object','properties':{'path':{'type':'string'}},'required':['path']},lambda path:read_workspace(workspace,path)))
registry.add(Tool('diagnostics','Inspect local node diagnostics.','DIAGNOSTICS',Risk.LOW,{'type':'object','properties':{}},lambda:diagnostics(workspace)))
registry.add(Tool('windows_exec','Run a PowerShell command on the local Windows node.','CONTROL_COMPUTER',Risk.HIGH,{'type':'object','properties':{'command':{'type':'string'},'timeout':{'type':'integer'}},'required':['command']},lambda command,timeout=30:windows_exec(workspace,command,timeout),destructive=True))
async def web_search(query,count=5): return {'status':'SUCCESS','results':await brave.search(query,count)}
registry.add(Tool('web_search','Search the live public web.','INTERNET_SEARCH',Risk.LOW,{'type':'object','properties':{'query':{'type':'string'},'count':{'type':'integer'}},'required':['query']},web_search))
agent=Agent(settings,store,policy,registry,provider,events,workspace,world,jobs)
async def task_worker(): await jobs.loop()
app=FastAPI(title='NOTSIP',version='0.3.0')
@app.on_event('startup')
async def startup(): app.state.worker=asyncio.create_task(task_worker())
@app.on_event('shutdown')
async def shutdown(): jobs.stop(); app.state.worker.cancel()
class Msg(BaseModel): message:str
class PairReq(BaseModel): code:str; device_id:str; name:str; platform:str; public_key:str
class HeartbeatReq(BaseModel): device_id:str; token:str
class TaskReq(BaseModel): objective:str; handler:str=''; priority:int=0; data:dict={}
async def auth(request:Request):
    if settings.api_key and request.headers.get('Authorization')!='Bearer '+settings.api_key: raise HTTPException(401,'Unauthorized')
def device_auth(device_id,token):
    expected=store.device_token_hash(device_id); return bool(expected and secrets.compare_digest(expected,hashlib.sha256(token.encode()).hexdigest()))
@app.get('/api/health')
async def health(_:None=Depends(auth)): return {'status':'ok','identity':'NOTSIP','version':'0.3.0','llm':provider.enabled,'autonomy_level':policy.level,'paired_devices':len(store.devices())}
@app.get('/api/status')
async def status(_:None=Depends(auth)): return {'identity':'NOTSIP','version':'0.3.0','llm_enabled':provider.enabled,'workspace':workspace,'tools':[t.name for t in registry.all()],'autonomy_level':policy.level,'world':world.snapshot(),'devices':store.devices()}
@app.get('/api/memory')
async def memory(q:str='',limit:int=20,_:None=Depends(auth)): return {'memories':store.search_memory(agent.user_id,q,max(1,min(limit,100)))}
@app.get('/api/audit')
async def audit(_:None=Depends(auth)): return {'audit':store.recent_audit()}
@app.get('/api/tasks')
async def tasks(_:None=Depends(auth)): return {'tasks':store.list_tasks()}
@app.post('/api/tasks')
async def create_task(body:TaskReq,_:None=Depends(auth)): return {'task_id':jobs.create(body.objective,body.handler,body.priority,body.data)}
@app.get('/api/pair/code')
async def pair_code(_:None=Depends(auth)): return {'code':pairing.create_code()}
@app.post('/api/pair/consume')
async def pair_consume(body:PairReq):
    token=pairing.consume(body.code,body.device_id,body.name,body.platform,body.public_key)
    if not token: raise HTTPException(400,'Invalid or expired pairing code')
    return {'paired':True,'device_id':body.device_id,'token':token}
@app.post('/api/devices/heartbeat')
async def heartbeat(body:HeartbeatReq):
    if not device_auth(body.device_id,body.token): raise HTTPException(401,'Invalid device token')
    store.heartbeat(body.device_id); return {'status':'SUCCESS','device_id':body.device_id}
@app.post('/api/message')
async def message(body:Msg,_:None=Depends(auth)):
    if not body.message.strip(): raise HTTPException(400,'message required')
    return await agent.handle(body.message)
@app.get('/api/search')
async def search(q:str,_:None=Depends(auth)):
    if not brave.enabled: raise HTTPException(503,'Brave Search is not configured')
    return {'results':await brave.search(q)}
@app.post('/api/events')
async def ingest(request:Request,x_notsip_signature:str|None=Header(default=None),_:None=Depends(auth)):
    raw=await request.body()
    if not webhook.verify(raw,x_notsip_signature): raise HTTPException(401,'invalid event signature')
    p=json.loads(raw); await events.publish(Event(p['type'],p.get('payload',{}),p.get('source','external'))); return {'accepted':True}
@app.websocket('/ws/events')
async def ws(socket:WebSocket):
    if settings.api_key and socket.headers.get('authorization')!='Bearer '+settings.api_key: await socket.close(code=4401); return
    await socket.accept(); q=events.subscribe()
    try:
        while True:
            e=await q.get(); await socket.send_json({'type':e.type,'payload':e.payload,'source':e.source,'timestamp':e.timestamp})
    except WebSocketDisconnect: pass
    finally: events.unsubscribe(q)
@app.get('/')
async def root(): return FileResponse(Path(__file__).resolve().parents[2]/'ui.html')
