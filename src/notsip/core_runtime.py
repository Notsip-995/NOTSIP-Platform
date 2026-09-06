from __future__ import annotations
import asyncio,hashlib,json,secrets
from datetime import datetime,timezone
from pathlib import Path
from fastapi import Depends,FastAPI,Header,HTTPException,Request,WebSocket,WebSocketDisconnect
from pydantic import BaseModel
from .config import settings
from .store import Store
from .policy import Policy,Risk
from .provider import Provider
from .tools import Registry,Tool,calc,Workspace,Windows,open_target
from .connectors import Web,Email,Calendar,OAuth,Browser
from .world import WorldModel
from .jobs import Scheduler
from .android_bridge import Pairing
from .agent import Agent
settings.ensure();ROOT=Path(settings.data_dir);WS=Workspace(ROOT/'workspace');store=Store(ROOT);policy=Policy(settings.autonomy_level);registry=Registry();provider=Provider(settings.llm_base_url,settings.llm_api_key,settings.llm_model);world=WorldModel(store);jobs=Scheduler(store);win=Windows(WS);web=Web(settings.brave_api_key);browser=Browser();emailc=Email(settings.smtp_host,settings.smtp_port,settings.imap_host,settings.email_username,settings.email_password);cal=Calendar();oauth=OAuth(settings.oauth_authorize_url,settings.oauth_token_url,settings.oauth_client_id,settings.oauth_client_secret,settings.oauth_redirect_uri,settings.oauth_scopes);pairing=Pairing(store);agent=Agent(settings,store,policy,registry,provider,world)
def reg(name,desc,cap,risk,schema,fn,destructive=False):registry.add(Tool(name,desc,cap,risk,schema,fn,destructive))
reg('calculator','Safe arithmetic.','COMPUTE',Risk.LOW,{'type':'object','properties':{'expr':{'type':'string'}},'required':['expr']},calc)
reg('list_files','List files in NOTSIP workspace.','READ_FILES',Risk.LOW,{'type':'object','properties':{'query':{'type':'string'}}},lambda query='':{'status':'SUCCESS','files':WS.list(query)})
reg('read_file','Read a text file in workspace.','READ_FILES',Risk.LOW,{'type':'object','properties':{'path':{'type':'string'}},'required':['path']},lambda path:{'status':'SUCCESS','content':WS.read(path)})
reg('write_file','Write a text file in workspace.','WRITE_FILES',Risk.MEDIUM,{'type':'object','properties':{'path':{'type':'string'},'content':{'type':'string'}},'required':['path','content']},lambda path,content:{'status':'SUCCESS','path':WS.write(path,content)})
reg('windows_exec','Execute PowerShell on the Windows node.','CONTROL_COMPUTER',Risk.HIGH,{'type':'object','properties':{'command':{'type':'string'},'timeout':{'type':'integer'}},'required':['command']},win.exec,True)
reg('desktop_screenshot','Capture the primary Windows desktop.','CONTROL_COMPUTER',Risk.MEDIUM,{'type':'object','properties':{'filename':{'type':'string'}}},win.screenshot)
reg('open_target','Open URL/file/application target using the OS.','CONTROL_COMPUTER',Risk.MEDIUM,{'type':'object','properties':{'target':{'type':'string'}},'required':['target']},open_target)
async def websearch(query,count=5):
    if not web.enabled:return {'status':'FAILURE','error':'web search not configured'}
    r=await web.search(query,count)
    for x in r:store.fact(x.get('title',''),'brave',x.get('url',''),.6,{'description':x.get('description','')})
    return {'status':'SUCCESS','results':r}
reg('web_search','Search the live web.','INTERNET_SEARCH',Risk.LOW,{'type':'object','properties':{'query':{'type':'string'},'count':{'type':'integer'}},'required':['query']},websearch)
reg('browser_extract','Open a public page with Playwright and extract visible text.','INTERNET_SEARCH',Risk.MEDIUM,{'type':'object','properties':{'url':{'type':'string'}},'required':['url']},browser.extract)
reg('email_send','Send an email via configured SMTP.','SEND_EMAIL',Risk.HIGH,{'type':'object','properties':{'to':{'type':'string'},'subject':{'type':'string'},'body':{'type':'string'}},'required':['to','subject','body']},emailc.send,True)
reg('email_search','Search a configured mailbox.','READ_EMAIL',Risk.LOW,{'type':'object','properties':{'mailbox':{'type':'string'},'criteria':{'type':'string'} }},emailc.search)
reg('calendar_parse','Parse a local ICS calendar file.','READ_CALENDAR',Risk.LOW,{'type':'object','properties':{'path':{'type':'string'}},'required':['path']},lambda path:{'status':'SUCCESS','events':cal.parse(WS.path(path))})
_worker=None
app=FastAPI(title='NOTSIP',version='0.7.0')
@app.on_event('startup')
async def startup():
    global _worker;_worker=asyncio.create_task(jobs.loop())
@app.on_event('shutdown')
async def shutdown():
    jobs.stop()
    if _worker:_worker.cancel()
async def auth(request:Request):
    if settings.api_key and request.headers.get('authorization')!='Bearer '+settings.api_key:raise HTTPException(401,'Unauthorized')
class Message(BaseModel):message:str
class Task(BaseModel):objective:str;handler:str='';delay:float=0;interval:float|None=None;data:dict={};priority:int=0
class Pair(BaseModel):code:str;device_id:str;name:str;platform:str;public_key:str=''
class Cmd(BaseModel):device_id:str;action:str;payload:dict={}
class Result(BaseModel):command_id:str;status:str;result:dict={}
@app.get('/')
async def root():return {'name':'NOTSIP','version':'0.7.0','status':'online'}
@app.get('/api/health')
async def health(_:None=Depends(auth)):return {'status':'ok','llm':provider.enabled,'memory':True,'world':True,'scheduler':True,'devices':len(store.devices())}
@app.get('/api/status')
async def status(_:None=Depends(auth)):return {'identity':'NOTSIP','version':'0.7.0','tools':[t.name for t in registry.all()],'autonomy_level':policy.level,'devices':store.devices(),'world':world.snapshot(),'capabilities':{'web':web.enabled,'email':emailc.enabled,'oauth':oauth.configured,'browser':True,'windows':True,'android_pairing':True}}
@app.get('/api/memory')
async def memory(q='',limit=20,_:None=Depends(auth)):return {'memories':store.memories(agent.user,q,max(1,min(int(limit),100)))}
@app.get('/api/facts')
async def facts(limit=100,_:None=Depends(auth)):return {'facts':store.facts(max(1,min(int(limit),500)))}
@app.get('/api/tasks')
async def tasks(_:None=Depends(auth)):return {'tasks':store.tasks()}
@app.post('/api/tasks')
async def create_task(body:Task,_:None=Depends(auth)):return {'task_id':jobs.create(body.objective,body.handler,body.delay,body.interval,body.data,body.priority)}
@app.post('/api/message')
async def message(body:Message,_:None=Depends(auth)):return await agent.handle(body.message)
@app.get('/api/pair/code')
async def pair_code(_:None=Depends(auth)):return {'code':pairing.create_code()}
@app.post('/api/pair/consume')
async def pair_consume(body:Pair):
    token=pairing.consume(body.code,body.device_id,body.name,body.platform,body.public_key)
    if not token:raise HTTPException(400,'invalid/expired pairing code')
    return {'device_id':body.device_id,'token':token}
@app.post('/api/devices/heartbeat')
async def heartbeat(device_id:str,token:str):
    if not store.device_token_valid(device_id,token):raise HTTPException(401,'invalid token')
    store.heartbeat(device_id);return {'status':'SUCCESS'}
@app.get('/api/devices/{device_id}/commands')
async def commands(device_id,token:str):
    if not store.device_token_valid(device_id,token):raise HTTPException(401,'invalid token')
    return {'commands':store.pull_commands(device_id)}
@app.post('/api/devices/command')
async def command(body:Cmd,_:None=Depends(auth)):
    if not store.row('SELECT id FROM devices WHERE id=?',(body.device_id,)):raise HTTPException(404,'device not paired')
    d=policy.decide(Risk.MEDIUM)
    if not d.allowed:return {'status':'PARTIAL_SUCCESS','approval_required':True,'error':d.reason}
    return {'status':'SUCCESS','command_id':store.queue_command(body.device_id,body.action,body.payload)}
@app.post('/api/devices/result')
async def result(body:Result):store.command_result(body.command_id,body.status,body.result);return {'status':'SUCCESS'}
@app.get('/api/audit')
async def audit(_:None=Depends(auth)):return {'audit':store.audit_recent()}
@app.websocket('/ws/events')
async def ws(sock:WebSocket):
    await sock.accept()
    try:
        while True:await sock.send_json({'type':'heartbeat','timestamp':datetime.now(timezone.utc).isoformat()});await asyncio.sleep(10)
    except WebSocketDisconnect:pass
