from __future__ import annotations
from pathlib import Path
from fastapi import Depends
from .execution_sandbox import ExecutionSandbox
from .execution_gate import ToolExecutionGate
from .policy import Risk
from .tools import Tool


def attach(app, require_auth, agent, registry, settings):
    sandbox = ExecutionSandbox(Path(settings.data_dir).resolve() / 'code-sandbox')
    if registry.get('execute_python') is None:
        registry.add(Tool(
            'execute_python',
            'Run authorized Python analysis in a disposable container with no network access and bounded resources.',
            'EXECUTE_CODE',
            Risk.HIGH,
            {'type':'object','properties':{'code':{'type':'string'},'timeout':{'type':'integer','minimum':1,'maximum':60},'max_output':{'type':'integer','minimum':1000,'maximum':200000}},'required':['code']},
            sandbox.run_python,
            True,
        ))
    ToolExecutionGate.wrap_registry(registry)

    @app.post('/api/code/execute')
    async def execute_python(payload: dict, _: None = Depends(require_auth)):
        return await agent.run_tool('execute_python', {
            'code': str(payload.get('code','')),
            'timeout': int(payload.get('timeout',20) or 20),
            'max_output': int(payload.get('max_output',50000) or 50000),
        })
    return sandbox
