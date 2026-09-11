from __future__ import annotations
import hashlib,os,time
from collections import Counter
from pathlib import Path
from fastapi import Depends,HTTPException

class Forensics:
    def __init__(self,workspace):self.workspace=Path(workspace).resolve()
    def scan(self,query='',limit=1000):
        q=str(query).lower();rows=[];ext=Counter()
        for p in self.workspace.rglob('*'):
            if not p.is_file():continue
            rel=str(p.relative_to(self.workspace)).replace('\\','/')
            if q and q not in rel.lower():continue
            try:
                data=p.read_bytes();st=p.stat();digest=hashlib.sha256(data).hexdigest();ext[p.suffix.lower() or '[no-extension]']+=1
                rows.append({'path':rel,'bytes':st.st_size,'mtime':st.st_mtime,'sha256':digest,'mode':oct(st.st_mode & 0o777),'suspicious':p.suffix.lower() in {'.ps1','.bat','.cmd','.vbs','.js','.hta'} and ('download' in rel.lower() or 'temp' in rel.lower())})
            except OSError as exc:rows.append({'path':rel,'error':str(exc)})
            if len(rows)>=max(1,min(int(limit),5000)):break
        return {'status':'SUCCESS','generated_at':time.time(),'root':str(self.workspace),'files':rows,'extensions':dict(ext),'suspicious_count':sum(1 for r in rows if r.get('suspicious'))}
    def investigate(self,query='',since=None,until=None,limit=1000):
        scanned=self.scan(query,limit);files=[f for f in scanned['files'] if 'sha256' in f]
        lo=float(since) if since is not None else 0;hi=float(until) if until is not None else float('inf')
        timed=[f for f in files if lo<=float(f.get('mtime',0))<=hi]
        suspicious=[f for f in timed if f.get('suspicious')]
        hypotheses=[]
        if suspicious:hypotheses.append({'hypothesis':'temporary/downloaded script activity warrants review','evidence':[x['path'] for x in suspicious],'confidence':0.55,'status':'UNVERIFIED'})
        if len(timed)>=2:
            deltas=sorted(float(b['mtime'])-float(a['mtime']) for a,b in zip(sorted(timed,key=lambda x:x['mtime']),sorted(timed,key=lambda x:x['mtime'])[1:]) if b['mtime']>=a['mtime'])
            hypotheses.append({'hypothesis':'clustered filesystem activity occurred in the requested window','evidence_count':len(timed),'median_gap':deltas[len(deltas)//2] if deltas else 0,'confidence':0.5,'status':'UNVERIFIED'})
        return {'status':'SUCCESS','query':query,'window':{'since':lo,'until':None if hi==float('inf') else hi},'collection':{'files':len(timed),'suspicious':len(suspicious)},'evidence':timed,'hypotheses':hypotheses,'verification':{'status':'NOT_PERFORMED','reason':'filesystem evidence alone cannot prove causality'},'report':{'generated_at':time.time(),'evidence_hash':hashlib.sha256(''.join(x.get('sha256','') for x in timed).encode()).hexdigest()}}

def attach(app,require_auth,workspace):
    service=Forensics(workspace)
    @app.get('/api/forensics/scan')
    async def scan(q:str='',limit:int=1000,_:None=Depends(require_auth)):return service.scan(q,limit)
    @app.get('/api/forensics/investigate')
    async def investigate(q:str='',since:float|None=None,until:float|None=None,limit:int=1000,_:None=Depends(require_auth)):
        if since is not None and until is not None and until<since:raise HTTPException(400,'until must be >= since')
        return service.investigate(q,since,until,limit)
