from __future__ import annotations
import json
from fastapi import Depends
from .actor_context import current_actor

_PUBLIC_FACT_SOURCES={'brave','public','web','system'}

def _own_task(task,actor):
    try:return json.loads(task.get('data') or '{}').get('actor','primary-user')==actor
    except Exception:return actor=='primary-user'

def _own_fact(fact,actor,store):
    if actor=='primary-user':return True
    source=str(fact.get('source') or '').lower()
    if source in _PUBLIC_FACT_SOURCES:return True
    try:meta=json.loads(fact.get('metadata') or '{}') if isinstance(fact.get('metadata'),str) else fact.get('metadata') or {}
    except Exception:meta={}
    if str(meta.get('actor') or '')==actor:return True
    device_id=str(meta.get('device_id') or '')
    return bool(device_id and store.device_owned_by(device_id,actor))

def attach(app,require_auth,store,policy,agent,settings,registry,web,emailc,auth):
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in {'/api/status','/api/facts'}]
    @app.get('/api/status')
    async def status(_:None=Depends(require_auth)):
        actor=current_actor();tasks=[x for x in store.tasks() if _own_task(x,actor)]
        return {'identity':'NOTSIP','version':'0.9.0','actor':actor,'autonomy_level':policy.level,'tools':[t.name for t in registry.all()],'devices':store.devices(actor),'world':__import__('notsip.app',fromlist=['world']).world.snapshot(actor),'tasks':tasks,'capabilities':{'llm':bool(getattr(agent.provider,'enabled',False)),'fallback_llm':bool(getattr(agent.provider,'fallback_enabled',False)),'voice_stt':bool(settings.stt_base_url and settings.stt_model),'voice_tts':bool(settings.tts_base_url and settings.tts_model),'vision':settings.vision_enabled,'windows_uia':True,'web_search':web.enabled,'email':emailc.enabled,'oidc':auth.oidc.configured,'android_pairing':True,'self_maintenance':settings.self_modify_enabled,'distributed_nodes':True,'recovery_checkpoints':True}}
    @app.get('/api/facts')
    async def facts(limit:int=100,_:None=Depends(require_auth)):
        actor=current_actor();rows=[x for x in store.facts(max(1,min(int(limit),500))) if _own_fact(x,actor,store)];return {'facts':rows[:max(1,min(int(limit),500))]}
