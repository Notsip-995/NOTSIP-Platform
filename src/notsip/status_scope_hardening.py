from __future__ import annotations
import json,platform
from fastapi import Depends,HTTPException
from .actor_context import current_actor

_PUBLIC_FACT_SOURCES={'brave','public','web','system'}

def _own_task(task,actor):
    try:return json.loads(task.get('data') or '{}').get('actor','')==actor
    except (TypeError,ValueError):return False

def _own_fact(fact,actor,store):
    if actor=='primary-user':return True
    source=str(fact.get('source') or '').lower()
    if source in _PUBLIC_FACT_SOURCES:return True
    try:meta=json.loads(fact.get('metadata') or '{}') if isinstance(fact.get('metadata'),str) else fact.get('metadata') or {}
    except (TypeError,ValueError):return False
    if str(meta.get('actor') or '')==actor:return True
    device_id=str(meta.get('device_id') or '')
    return bool(device_id and store.device_owned_by(device_id,actor))

def attach(app,require_auth,store,policy,agent,settings,registry,web,emailc,auth):
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in {'/api/status','/api/facts','/api/remote/satellite'}]
    @app.get('/api/status')
    async def status(_:None=Depends(require_auth)):
        actor=current_actor();tasks=[x for x in store.tasks() if _own_task(x,actor)];live_policy=getattr(agent,'policy',policy);level=getattr(live_policy,'current_level',getattr(live_policy,'level',0));devices=store.devices(actor)
        recovery_ok=False
        try:recovery_ok=bool(getattr(__import__('notsip.app',fromlist=['recovery']),'recovery').verify_latest().get('valid'))
        except Exception:recovery_ok=False
        distributed_nodes=False
        try:
            nodes=getattr(__import__('notsip.app',fromlist=['nodes']),'nodes');distributed_nodes=any(str(n.get('status','')).upper()=='ONLINE' for n in nodes.reconcile(actor))
        except (AttributeError,TypeError,ValueError,RuntimeError):distributed_nodes=False
        return {'identity':'NOTSIP','version':'0.9.0','actor':actor,'autonomy_level':level,'tools':[t.name for t in registry.all()],'devices':devices,'world':__import__('notsip.app',fromlist=['world']).world.snapshot(actor),'tasks':tasks,'capabilities':{'llm':bool(getattr(agent.provider,'enabled',False)),'fallback_llm':bool(getattr(agent.provider,'fallback_enabled',False)),'voice_stt':bool(settings.stt_base_url and settings.stt_model),'voice_tts':bool(settings.tts_base_url and settings.tts_model),'vision':bool(settings.vision_enabled),'perception':bool(settings.perception_enabled),'windows_uia':platform.system()=='Windows','web_search':web.enabled,'email':emailc.enabled,'oidc':auth.oidc.configured,'android_pairing':bool(devices),'self_maintenance':bool(settings.self_modify_enabled),'distributed_nodes':distributed_nodes,'recovery_checkpoints':recovery_ok}}
    @app.get('/api/facts')
    async def facts(limit:int=100,_:None=Depends(require_auth)):
        actor=current_actor();n=max(1,min(int(limit),500));rows=[x for x in store.facts(n) if _own_fact(x,actor,store)];return {'facts':rows[:n]}
    @app.get('/api/remote/satellite')
    async def satellite_route(bbox:str,start:str,end:str,scene_id:str='',_:None=Depends(require_auth)):
        if current_actor()!='primary-user':raise HTTPException(403,'primary administrative actor required for satellite access')
        if not str(getattr(settings,'remote_sensing_url','')).strip() or not str(getattr(settings,'remote_sensing_token','')).strip():
            return {'status':'BLOCKED_BY_EXTERNAL_ENVIRONMENT','error':'authorized remote-sensing provider is not configured'}
        return await agent.run_tool('satellite_query',{'bbox':bbox,'start':start,'end':end,'scene_id':scene_id})
    if registry is not None:
        from .external_adapters import RemoteSensingAdapter,AdapterUnavailable
        from .policy import Risk
        from .tools import Tool
        from .execution_gate import ToolExecutionGate
        sensing=RemoteSensingAdapter(getattr(settings,'remote_sensing_url',''),getattr(settings,'remote_sensing_token',''))
        def satellite_query(bbox,start,end,scene_id=''):
            if current_actor()!='primary-user':raise PermissionError('primary administrative actor required for satellite access')
            if not sensing.configured:raise AdapterUnavailable('authorized remote-sensing provider is not configured')
            return sensing.satellite_query(bbox,start,end,scene_id,authorized=True)
        registry.add(Tool('satellite_query','Query an authorized satellite/remote-sensing provider; lawful access is controlled server-side.','INTERNET_SEARCH',Risk.HIGH,{'type':'object','properties':{'bbox':{'type':'string'},'start':{'type':'string'},'end':{'type':'string'},'scene_id':{'type':'string'}},'required':['bbox','start','end']},satellite_query))
        ToolExecutionGate.wrap_registry(registry)
