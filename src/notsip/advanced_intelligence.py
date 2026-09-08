from __future__ import annotations
from fastapi import Depends, HTTPException
from .event_priority import EventPriorityEngine
from .predictive_maintenance import PredictiveMaintenance
from .task_decomposer import TaskDecomposer
from .information_fusion import InformationFusion


def attach(app, require_auth, store, web, agent, registry=None, events=None):
    decomposer=TaskDecomposer(); predictor=PredictiveMaintenance(); priority=EventPriorityEngine()
    fusion=InformationFusion(store,web)
    @app.get('/api/intelligence/decompose')
    async def decompose(objective:str,_:None=Depends(require_auth)):
        return decomposer.decompose(objective)
    @app.post('/api/intelligence/priority')
    async def classify_event(payload:dict,_:None=Depends(require_auth)):
        return priority.classify(importance=payload.get('importance',0),urgency=payload.get('urgency',0),relevance=payload.get('relevance',0),explicit_interrupt=payload.get('explicit_interrupt',False),event_type=payload.get('event_type','')).__dict__
    @app.post('/api/intelligence/predict')
    async def predict(payload:dict,_:None=Depends(require_auth)):
        samples=payload.get('samples') or []
        metric=str(payload.get('metric') or '').strip()
        if not metric: raise HTTPException(400,'metric is required')
        return predictor.evaluate(samples,metric,warning_slope=float(payload.get('warning_slope',0.1)),failure_threshold=payload.get('failure_threshold'))
    @app.get('/api/information/fuse')
    async def fused_information(q:str,count:int=5,_:None=Depends(require_auth)):
        if not q.strip():raise HTTPException(400,'query is required')
        return await fusion.fuse(q,count)
    if registry is not None:
        from .policy import Risk
        registry.add(__import__('notsip.tools',fromlist=['Tool']).Tool('decompose_task','Decompose a complex objective into ordered subtasks.','INTELLIGENCE',Risk.LOW,{'type':'object','properties':{'objective':{'type':'string'}},'required':['objective']},decomposer.decompose))
        registry.add(__import__('notsip.tools',fromlist=['Tool']).Tool('prioritize_event','Classify event importance, urgency and user relevance.','INTELLIGENCE',Risk.LOW,{'type':'object','properties':{'importance':{'type':'number'},'urgency':{'type':'number'},'relevance':{'type':'number'},'explicit_interrupt':{'type':'boolean'},'event_type':{'type':'string'}}},lambda importance=0,urgency=0,relevance=0,explicit_interrupt=False,event_type='':priority.classify(importance=importance,urgency=urgency,relevance=relevance,explicit_interrupt=explicit_interrupt,event_type=event_type).__dict__))
    return {'decomposer':decomposer,'predictor':predictor,'priority':priority,'fusion':fusion}
