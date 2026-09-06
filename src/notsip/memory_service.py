from __future__ import annotations
import time

KINDS={'episodic','semantic','procedural','working','preference','relationship','system','perception'}

class MemoryService:
    def __init__(self,store,user_id='primary-user'):self.store=store;self.user_id=user_id
    def classify(self,kind):return kind if kind in KINDS else 'semantic'
    def remember(self,content,kind='semantic',weight=.8,source='service',provenance=None):
        self.store.remember(self.user_id,self.classify(kind),content,float(max(0,min(1,weight))),source,provenance or {});return {'status':'SUCCESS','kind':self.classify(kind)}
    def decay(self,half_life_days=90):
        now=time.time();factor=lambda age:0.5**(age/max(0.001,half_life_days*86400))
        rows=self.store.rows('SELECT id,weight,ts FROM memories WHERE user_id=?',(self.user_id,));changed=0
        for r in rows:
            nw=max(.05,min(1,float(r['weight'])*factor(max(0,now-float(r['ts'])))))
            if abs(nw-float(r['weight']))>.01:self.store.exec('UPDATE memories SET weight=? WHERE id=?',(nw,r['id']));changed+=1
        return {'status':'SUCCESS','changed':changed}
    def consolidate(self,limit=200):
        rows=self.store.rows('SELECT kind,content,weight,source,provenance FROM memories WHERE user_id=? ORDER BY weight DESC,ts DESC LIMIT ?',(self.user_id,limit));seen=set();kept=[]
        for r in rows:
            key=' '.join(str(r['content']).lower().split())
            if key in seen:continue
            seen.add(key);kept.append(r)
        return {'status':'SUCCESS','examined':len(rows),'unique':len(kept),'duplicates_removed':len(rows)-len(kept)}
    def snapshot(self,limit=200):
        return {'memory_kinds':sorted({r['kind'] for r in self.store.rows('SELECT kind FROM memories WHERE user_id=?',(self.user_id,))}),'items':self.store.memories(self.user_id,'',limit)}
