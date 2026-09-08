from __future__ import annotations
from fastapi import Depends, HTTPException
from .event_priority import EventPriorityEngine
from .predictive_maintenance import PredictiveMaintenance
from .task_decomposer import TaskDecomposer
from .resource_router import ResourceRouter,RobotGateway
from .external_adapters import RemoteComputeAdapter,RemoteSensingAdapter,HomeAdapter,BiometricTelemetryAdapter,AdapterUnavailable


def attach(app, require_auth, store, web, agent, registry=None, events=None, settings=None):
    decomposer=TaskDecomposer(); predictor=PredictiveMaintenance(); priority=EventPriorityEngine(); router=ResourceRouter(store); robots=RobotGateway(store,router)
    settings=settings or getattr(agent,'settings',None)
    remote_compute=RemoteComputeAdapter(getattr(settings,'remote_compute_url',''),getattr(settings,'remote_compute_token',''))
    remote_sensing=RemoteSensingAdapter(getattr(settings,'remote_sensing_url',''),getattr(settings,'remote_sensing_token',''))
    home=HomeAdapter(getattr(settings,'home_adapter_url',''),getattr(settings,'home_adapter_token',''))
    biometrics=BiometricTelemetryAdapter(getattr(settings,'biometric_adapter_url',''),getattr(settings,'biometric_adapter_token',''))
    @app.get('/api/intelligence/decompose')
    async def decompose(objective:str,_:None=Depends(require_auth)): return decomposer.decompose(objective)
    @app.post('/api/intelligence/priority')
    async def classify_event(payload:dict,_:None=Depends(require_auth)):
        return priority.classify(importance=payload.get('importance',0),urgency=payload.get('urgency',0),relevance=payload.get('relevance',0),explicit_interrupt=payload.get('explicit_interrupt',False),event_type=payload.get('event_type','')).__dict__
    @app.post('/api/intelligence/predict')
    async def predict(payload:dict,_:None=Depends(require_auth)):
        samples=payload.get('samples') or [];metric=str(payload.get('metric') or '').strip()
        if not metric: raise HTTPException(400,'metric is required')
        return predictor.evaluate(samples,metric,warning_slope=float(payload.get('warning_slope',0.1)),failure_threshold=payload.get('failure_threshold'))
    @app.get('/api/resources')
    async def resources(_:None=Depends(require_auth)): return {'status':'SUCCESS','nodes':router.snapshot()}
    @app.get('/api/resources/select')
    async def select_resource(capability:str,prefer_local:bool=True,_:None=Depends(require_auth)):
        if not capability.strip():raise HTTPException(400,'capability is required')
        return router.select(capability.strip(),prefer_local=prefer_local)
    @app.post('/api/remote/compute')
    async def remote_compute(payload:dict,_:None=Depends(require_auth)):
        try:return await remote_compute.submit(str(payload.get('job_type','data_processing')),payload.get('payload') or {})
        except AdapterUnavailable as exc:return {'status':'BLOCKED_BY_EXTERNAL_ENVIRONMENT','error':str(exc)}
    @app.get('/api/remote/sensing')
    async def remote_sensing(query:dict,_:None=Depends(require_auth)):
        try:return await remote_sensing.query(query)
        except AdapterUnavailable as exc:return {'status':'BLOCKED_BY_EXTERNAL_ENVIRONMENT','error':str(exc)}
    @app.post('/api/home/command')
    async def home_command(payload:dict,_:None=Depends(require_auth)):
        try:return await home.command(str(payload.get('device_id','')),str(payload.get('action','')),payload.get('payload') or {})
        except AdapterUnavailable as exc:return {'status':'BLOCKED_BY_EXTERNAL_ENVIRONMENT','error':str(exc)}
    @app.get('/api/biometrics/latest')
    async def biometric_latest(_:None=Depends(require_auth)):
        try:return await biometrics.latest()
        except AdapterUnavailable as exc:return {'status':'BLOCKED_BY_EXTERNAL_ENVIRONMENT','error':str(exc),'is_diagnosis':False}
    @app.get('/api/robots/{node_id}/status')
    async def robot_status(node_id:str,_:None=Depends(require_auth)): return robots.status(node_id)
    @app.post('/api/robots/{node_id}/command')
    async def robot_command(node_id:str,payload:dict,_:None=Depends(require_auth)):
        return robots.command(node_id,str(payload.get('action','')),payload.get('payload') or {})
    if registry is not None:
        from .policy import Risk
        from .tools import Tool
        registry.add(Tool('decompose_task','Decompose a complex objective into ordered subtasks.','INTELLIGENCE',Risk.LOW,{'type':'object','properties':{'objective':{'type':'string'}},'required':['objective']},decomposer.decompose))
        registry.add(Tool('prioritize_event','Classify event importance, urgency and user relevance.','INTELLIGENCE',Risk.LOW,{'type':'object','properties':{'importance':{'type':'number'},'urgency':{'type':'number'},'relevance':{'type':'number'},'explicit_interrupt':{'type':'boolean'},'event_type':{'type':'string'}}},lambda importance=0,urgency=0,relevance=0,explicit_interrupt=False,event_type='':priority.classify(importance=importance,urgency=urgency,relevance=relevance,explicit_interrupt=explicit_interrupt,event_type=event_type).__dict__))
        registry.add(Tool('select_resource','Select a healthy authorized execution node.','CONTROL_SERVER',Risk.MEDIUM,{'type':'object','properties':{'capability':{'type':'string'},'prefer_local':{'type':'boolean'}},'required':['capability']},router.select))
        registry.add(Tool('remote_compute','Submit authorized compute work to the configured remote compute provider.','COMPUTE',Risk.MEDIUM,{'type':'object','properties':{'job_type':{'type':'string'},'payload':{'type':'object'}},'required':['job_type']},remote_compute.submit))
        registry.add(Tool('remote_sensing','Query the configured lawful remote-sensing provider.','INTERNET_SEARCH',Risk.MEDIUM,{'type':'object','properties':{'params':{'type':'object'}}},remote_sensing.query))
        registry.add(Tool('home_command','Control an authorized building/home device through the configured provider.','CONTROL_HOME',Risk.HIGH,{'type':'object','properties':{'device_id':{'type':'string'},'action':{'type':'string'},'payload':{'type':'object'}},'required':['device_id','action']},home.command,True))
        registry.add(Tool('biometric_latest','Read authorized biometric telemetry; never a medical diagnosis.','ACCESS_CAMERA',Risk.MEDIUM,{'type':'object','properties':{}},biometrics.latest))
        registry.add(Tool('robot_command','Queue an authorized command for a connected robot and await device verification.','CONTROL_ROBOTICS',Risk.HIGH,{'type':'object','properties':{'node_id':{'type':'string'},'action':{'type':'string'},'payload':{'type':'object'}},'required':['node_id','action']},lambda node_id,action,payload=None:robots.command(node_id,action,payload),True))
        ToolExecutionGate=__import__('notsip.execution_gate',fromlist=['ToolExecutionGate']).ToolExecutionGate;ToolExecutionGate.wrap_registry(registry)
    return {'decomposer':decomposer,'predictor':predictor,'priority':priority,'router':router,'robots':robots,'remote_compute':remote_compute,'remote_sensing':remote_sensing,'home':home,'biometrics':biometrics}
