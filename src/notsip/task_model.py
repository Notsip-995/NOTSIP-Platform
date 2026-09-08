from __future__ import annotations
from dataclasses import dataclass,field,asdict
from typing import Any

@dataclass
class TaskRecord:
    objective:str
    requester:str='primary-user'
    context:dict[str,Any]=field(default_factory=dict)
    deadline:float|None=None
    priority:int=0
    constraints:list[str]=field(default_factory=list)
    required_tools:list[str]=field(default_factory=list)
    permissions:list[str]=field(default_factory=list)
    subtasks:list[dict[str,Any]]=field(default_factory=list)
    state:str='PENDING'
    result:dict[str,Any]=field(default_factory=dict)
    verification:dict[str,Any]=field(default_factory=dict)
    def to_dict(self):return asdict(self)
    @classmethod
    def from_data(cls,objective,data=None,**overrides):
        raw=dict(data or {});raw.update(overrides);raw.setdefault('objective',objective)
        allowed={f.name for f in cls.__dataclass_fields__.values()};return cls(**{k:v for k,v in raw.items() if k in allowed})
