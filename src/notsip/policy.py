from dataclasses import dataclass
from .config import settings, DEFAULT_CAPABILITY_LEVELS

class Risk:
    LOW=0;MEDIUM=1;HIGH=2;CRITICAL=3

@dataclass
class Decision:
    allowed: bool
    needs_confirmation: bool
    reason: str
    capability: str=''
    required_level: int=0

class Policy:
    def __init__(self,level=None):
        self.level=max(0,min(4,int(settings.autonomy_level if level is None else level)))
    @property
    def current_level(self):
        return max(0,min(4,int(settings.autonomy_level)))
    def capability_level(self,capability):
        configured=getattr(settings,'capability_levels',{}) or {}
        raw=configured.get(capability,DEFAULT_CAPABILITY_LEVELS.get(capability,4))
        return max(0,min(4,int(raw)))
    def decide(self,risk,destructive=False,capability=''):
        level=self.current_level
        self.level=level
        required=self.capability_level(capability) if capability else 0
        if capability and level<required:
            return Decision(False,True,f'capability {capability} requires autonomy level {required} (current {level})',capability,required)
        if risk==Risk.LOW:
            return Decision(True,False,'allowed',capability,required)
        if risk==Risk.MEDIUM:
            if level>=3:return Decision(True,False,'allowed',capability,required)
            return Decision(False,True,'medium-risk action requires autonomy level 3 or approval',capability,required)
        if risk==Risk.HIGH or destructive:
            if level>=4:return Decision(True,False,'allowed at autonomy level 4',capability,required)
            return Decision(False,True,'high-risk action requires autonomy level 4 or approval',capability,required)
        return Decision(False,True,'critical action blocked',capability,required)
