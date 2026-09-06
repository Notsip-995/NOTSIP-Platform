from enum import IntEnum
class Risk(IntEnum): LOW=0; MEDIUM=1; HIGH=2; CRITICAL=3
class Decision:
    def __init__(self,allowed,needs_confirmation=False,reason=''): self.allowed=allowed; self.needs_confirmation=needs_confirmation; self.reason=reason
class Policy:
    def __init__(self,level): self.level=int(level)
    def decide(self,risk,destructive=False):
        if destructive and self.level<3: return Decision(False,True,'Destructive operation requires autonomy level 3 or explicit approval')
        if risk>=Risk.CRITICAL and self.level<4: return Decision(False,True,'Critical operation requires autonomy level 4 or explicit approval')
        if risk>=Risk.HIGH and self.level<3: return Decision(False,True,'High-risk operation requires autonomy level 3 or explicit approval')
        return Decision(True)
