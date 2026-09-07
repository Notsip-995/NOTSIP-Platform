from dataclasses import dataclass
from .config import settings

class Risk:
    LOW=0;MEDIUM=1;HIGH=2;CRITICAL=3

@dataclass
class Decision:
    allowed: bool
    needs_confirmation: bool
    reason: str

class Policy:
    def __init__(self,level=None):
        self.level=max(0,min(4,int(settings.autonomy_level if level is None else level)))
    @property
    def current_level(self):
        return max(0,min(4,int(settings.autonomy_level)))
    def decide(self,risk,destructive=False):
        level=self.current_level
        self.level=level
        if risk==Risk.LOW:
            return Decision(True,False,'allowed')
        if risk==Risk.MEDIUM:
            if level>=3:return Decision(True,False,'allowed')
            return Decision(False,True,'medium-risk action requires autonomy level 3 or approval')
        if risk==Risk.HIGH or destructive:
            if level>=4:return Decision(True,False,'allowed at autonomy level 4')
            return Decision(False,True,'high-risk action requires autonomy level 4 or approval')
        return Decision(False,True,'critical action blocked')
