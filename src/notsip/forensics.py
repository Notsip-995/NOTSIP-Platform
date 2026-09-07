from __future__ import annotations
import hashlib, os, time
from pathlib import Path
from collections import Counter
from fastapi import Depends

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

def attach(app,require_auth,workspace):
    service=Forensics(workspace)
    @app.get('/api/forensics/scan')
    async def scan(q:str='',limit:int=1000,_:None=Depends(require_auth)):return service.scan(q,limit)
