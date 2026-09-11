from __future__ import annotations
from .policy import Risk
from .tools import Tool
from .execution_gate import ToolExecutionGate

def attach(registry,win):
    registry.add(Tool('windows_exec','Execute PowerShell on Windows; optionally verify an explicit postcondition.','CONTROL_COMPUTER',Risk.HIGH,{'type':'object','properties':{'command':{'type':'string'},'timeout':{'type':'integer','minimum':1,'maximum':180},'verify_command':{'type':'string'}},'required':['command']},win.exec,True))
    ToolExecutionGate.wrap_registry(registry)
