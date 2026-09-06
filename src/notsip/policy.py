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
        if risk==Risk.LOW:return Decision(True,False,'allowed')
        if risk==Risk.MEDIUM:return Decision(level>=2,level<3,'approval required' if level<3 else 'allowed')
        if risk==Risk.HIGH or destructive:return Decision(level>=4,True,'high-risk action requires autonomy level 4')
        return Decision(False,True,'critical action blocked')
