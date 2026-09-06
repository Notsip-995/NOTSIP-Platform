from __future__ import annotations
from dataclasses import dataclass, field
from uuid import uuid4
from .policy import Risk

@dataclass
class PlanStep:
    id: str
    action: str
    capability: str
    risk: Risk
    status: str='PENDING'
    result: dict|None=None

@dataclass
class Plan:
    goal: str
    steps: list[PlanStep]=field(default_factory=list)
    plan_id: str=field(default_factory=lambda:str(uuid4()))

class Planner:
    def create(self, goal: str, steps: list[dict]) -> Plan:
        return Plan(goal,[PlanStep(str(uuid4()),s['action'],s.get('capability',''),Risk(s.get('risk',0))) for s in steps])
