from __future__ import annotations
from fastapi import Depends, HTTPException
from .business_admin import BusinessAdminAdapter
from .policy import Risk
from .tools import Tool


def attach(app,require_auth,agent,registry,settings):
    adapter=BusinessAdminAdapter(getattr(settings,'business_admin_url',''),getattr(settings,'business_admin_token',''))
    if registry.get('business_query') is None:
        registry.add(Tool('business_query','Query an authorized configured business or enterprise system without mutating it.','BUSINESS_ADMIN',Risk.LOW,{'type':'object','properties':{'operation':{'type':'string'},'params':{'type':'object'}},'required':['operation']},adapter.query))
    if registry.get('business_action') is None:
        registry.add(Tool('business_action','Perform a high-impact mutation in an authorized configured business or enterprise system.','BUSINESS_ADMIN',Risk.HIGH,{'type':'object','properties':{'operation':{'type':'string'},'payload':{'type':'object'}},'required':['operation']},adapter.action,True))
    from .execution_gate import ToolExecutionGate
    ToolExecutionGate.wrap_registry(registry)
    @app.get('/api/business/query')
    async def business_query(operation:str='status',params:dict|None=None,_:None=Depends(require_auth)):
        return await agent.run_tool('business_query',{'operation':operation,'params':params or {}})
    @app.post('/api/business/action')
    async def business_action(payload:dict,_:None=Depends(require_auth)):
        operation=str(payload.get('operation','')).strip()
        if not operation:raise HTTPException(400,'operation is required')
        return await agent.run_tool('business_action',{'operation':operation,'payload':payload.get('payload') or {}})
    return adapter
