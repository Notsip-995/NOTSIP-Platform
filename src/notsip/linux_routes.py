from __future__ import annotations
from fastapi import Depends
from pathlib import Path
from .linux_automation import LinuxAutomation
from .policy import Risk
from .tools import Tool
from .execution_gate import ToolExecutionGate

def attach(app,require_auth,agent,registry,settings):
    automation=LinuxAutomation(Path(settings.data_dir).resolve()/'workspace')
    if registry.get('linux_exec') is None:
        registry.add(Tool('linux_exec','Execute a non-elevated command on a connected Linux host; requires approval.','CONTROL_SERVER',Risk.HIGH,{'type':'object','properties':{'command':{'type':'string'},'timeout':{'type':'integer','minimum':1,'maximum':180}},'required':['command']},automation.exec,True))
    if registry.get('linux_open') is None:
        registry.add(Tool('linux_open','Open an authorized Linux workspace path; resulting application state is reported as unknown until observed.','CONTROL_COMPUTER',Risk.MEDIUM,{'type':'object','properties':{'relative':{'type':'string'}},'required':['relative']},automation.open_path))
    ToolExecutionGate.wrap_registry(registry)
    @app.post('/api/linux/exec')
    async def linux_exec(payload:dict,_:None=Depends(require_auth)):
        return await agent.run_tool('linux_exec',{'command':str(payload.get('command','')),'timeout':int(payload.get('timeout',60))})
    @app.post('/api/linux/open')
    async def linux_open(payload:dict,_:None=Depends(require_auth)):
        return await agent.run_tool('linux_open',{'relative':str(payload.get('relative',''))})
    return automation
