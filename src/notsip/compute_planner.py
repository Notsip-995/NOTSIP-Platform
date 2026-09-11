from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ComputeDecision:
    placement: str
    reason: str
    capability: str
    node_id: str | None = None
    requires_remote_provider: bool = False

class ComputePlanner:
    def __init__(self,resource_router,remote_compute):self.router=resource_router;self.remote=remote_compute
    def choose(self,capability='COMPUTE',prefer_local=True):
        local=self.router.select(capability,prefer_local=prefer_local)
        if local.get('status')=='SUCCESS':
            node=local['node'];return ComputeDecision('LOCAL',f"selected healthy authorized node {node['id']}",capability,node['id'],False)
        if self.remote.configured:return ComputeDecision('REMOTE','no suitable local node; configured remote compute provider available',capability,None,True)
        return ComputeDecision('BLOCKED',local.get('error','no compute resource available'),capability,None,True)
