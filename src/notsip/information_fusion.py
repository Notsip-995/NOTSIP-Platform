from __future__ import annotations
import time
from collections import defaultdict
from difflib import SequenceMatcher
from fastapi import Depends, HTTPException

class InformationFusion:
    """Fuse stored and remote evidence without treating duplicate sources as independent."""
    def __init__(self,store,web,similarity_threshold=0.90):self.store,self.web=store,web;self.similarity_threshold=float(similarity_threshold)
    @staticmethod
    def _norm(text):return ' '.join(str(text or '').lower().split())
    @staticmethod
    def _authority(row,default_originality=1.0):
        metadata=row.get('metadata') or {}
        originality=float(row.get('originality',metadata.get('originality',default_originality)) or 0)
        corroboration=int(row.get('corroboration',metadata.get('corroboration',0)) or 0)
        return max(0.0,min(1.0,originality)),max(0,corroboration)
    def stored(self,query,limit=50):
        q=str(query).lower();facts=self.store.facts(limit)
        return [f for f in facts if q in str(f.get('statement','')).lower() or q in str(f.get('url','')).lower()]
    def _cluster(self,evidence):
        clusters=[]
        for row in evidence:
            key=self._norm(row.get('statement',''));placed=False
            for c in clusters:
                if SequenceMatcher(None,key,self._norm(c[0].get('statement',''))).ratio()>=self.similarity_threshold:c.append(row);placed=True;break
            if not placed:clusters.append([row])
        claims=[]
        for c in clusters:
            sources=defaultdict(list)
            for row in c:sources[row.get('source','unknown')].append(row)
            best=max(c,key=lambda x:float(x.get('confidence',0)))
            originality,corroboration=self._authority(best)
            independent=len(sources);source_corrob=max(corroboration,independent)
            score=min(1.0,0.50*float(best.get('confidence',0))+0.25*min(1,independent/3)+0.15*originality+0.10*min(1,source_corrob/3))
            claims.append({'statement':best.get('statement',''),'support':len(c),'independent_sources':independent,'sources':sorted(sources),'confidence':score,'best_source_confidence':float(best.get('confidence',0)),'originality':originality,'corroboration':source_corrob,'timestamps':sorted(str(x.get('retrieved','')) for x in c if x.get('retrieved'))})
        return sorted(claims,key=lambda x:x['confidence'],reverse=True)
    def _conflicts(self,evidence):
        by_subject=defaultdict(list)
        for row in evidence:
            metadata=row.get('metadata') or {};subject=self._norm(metadata.get('subject',''))
            if subject:by_subject[subject].append(row)
        out=[]
        for subject,rows in by_subject.items():
            unique=[]
            for row in rows:
                statement=self._norm(row.get('statement',''))
                if statement not in {self._norm(x) for x in unique}:unique.append(row.get('statement',''))
            if len(unique)>1:
                out.append({'subject':subject,'statements':unique,'sources':sorted({r.get('source','unknown') for r in rows}),'status':'CONFLICTING_EVIDENCE','confidence_by_statement':[{'statement':s,'sources':sorted({r.get('source','unknown') for r in rows if self._norm(r.get('statement',''))==self._norm(s)})} for s in unique]})
        return out
    async def fuse(self,query,count=5):
        query=str(query).strip()
        if not query:raise ValueError('query is required')
        local=self.stored(query,200);remote=[]
        if self.web.enabled:
            remote=await self.web.search(query,max(1,min(int(count),20)))
            for item in remote:
                self.store.fact(item.get('title',''),'brave',item.get('url',''),.55,{'query':query,'retrieved_at':time.time(),'originality':1.0,'corroboration':0})
        evidence=[]
        for f in local:
            metadata=f.get('metadata') or {};originality,corroboration=self._authority(f)
            evidence.append({'kind':'stored_fact','statement':f.get('statement',''),'source':f.get('source',''),'url':f.get('url',''),'confidence':f.get('confidence',0.0),'retrieved':f.get('retrieved'),'metadata':metadata,'originality':originality,'corroboration':corroboration})
        evidence += [{'kind':'web','statement':r.get('title',''),'source':'brave','url':r.get('url',''),'confidence':.55,'description':r.get('description',''),'retrieved':time.time(),'metadata':{'query':query},'originality':1.0,'corroboration':0} for r in remote]
        return {'status':'SUCCESS','query':query,'evidence':evidence,'claims':self._cluster(evidence),'conflicts':self._conflicts(evidence),'counts':{'stored':len(local),'web':len(remote)},'generated_at':time.time()}

def attach(app,require_auth,store,web):
    service=InformationFusion(store,web)
    @app.get('/api/information/fuse')
    async def information_fuse(q:str,count:int=5,_:None=Depends(require_auth)):
        q=q.strip()
        if not q:raise HTTPException(400,'query is required')
        return await service.fuse(q,count)
    @app.get('/api/information/stored')
    async def information_stored(q:str,limit:int=50,_:None=Depends(require_auth)):return {'query':q,'evidence':service.stored(q,max(1,min(int(limit),200)))}
