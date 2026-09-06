from dataclasses import dataclass
class Risk:LOW=0;MEDIUM=1;HIGH=2;CRITICAL=3
@dataclass
class Decision:allowed:bool;needs_confirmation:bool;reason:str
class Policy:
    def __init__(self,level):self.level=max(0,min(4,int(level)))
    def decide(self,risk,destructive=False):
        if risk==Risk.LOW:return Decision(True,False,'allowed')
        if risk==Risk.MEDIUM:return Decision(self.level>=2,self.level<3,'approval required' if self.level<3 else 'allowed')
        if risk==Risk.HIGH or destructive:return Decision(self.level>=4,True,'high-risk action requires autonomy level 4')
        return Decision(False,True,'critical action blocked')
