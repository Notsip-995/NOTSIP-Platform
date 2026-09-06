from __future__ import annotations
from dataclasses import dataclass, asdict

MEMORY_KINDS=('short_term','episodic','semantic','preference','procedural','system')
@dataclass
class Memory:
    kind:str; content:str; weight:float=.8; source:str='user'; importance:float=.5
class MemoryManager:
    def __init__(self,store): self.store=store
    def add(self,user_id,kind,content,weight=.8,source='user',importance=.5):
        if kind not in MEMORY_KINDS: raise ValueError(f'unsupported memory kind: {kind}')
        m=Memory(kind,content,weight,source,importance); self.store.remember(user_id,**asdict(m)); return m
    def search(self,user_id,query='',limit=20): return self.store.search_memory(user_id,query,limit)
    def summarize(self,user_id,limit=50):
        rows=self.store.search_memory(user_id,'',limit); out={k:[] for k in MEMORY_KINDS}
        for row in rows: out.setdefault(row['kind'],[]).append(row)
        return out
