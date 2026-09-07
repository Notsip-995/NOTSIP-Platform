from __future__ import annotations
import json, statistics, time
from pathlib import Path

class HealthAnalytics:
    def __init__(self,root):
        self.path=Path(root)/'runtime'/'telemetry.jsonl';self.path.parent.mkdir(parents=True,exist_ok=True)
    def record(self,snapshot):
        row=dict(snapshot);row['recorded_at']=time.time()
        with self.path.open('a',encoding='utf-8') as f:f.write(json.dumps(row,sort_keys=True)+'\n')
        self._trim(5000);return row
    def _trim(self,max_rows):
        lines=self.path.read_text(encoding='utf-8').splitlines()
        if len(lines)>max_rows:self.path.write_text('\n'.join(lines[-max_rows:])+'\n',encoding='utf-8')
    def samples(self,limit=500):
        if not self.path.exists():return []
        out=[]
        for line in self.path.read_text(encoding='utf-8').splitlines()[-max(1,min(int(limit),5000)):]:
            try:out.append(json.loads(line))
            except Exception:pass
        return out
    def analyze(self,limit=120):
        rows=self.samples(limit);warnings=[]
        for row in rows[-30:]:
            mem=(row.get('memory') or {}).get('percent')
            free=(row.get('disk') or {}).get('free');total=(row.get('disk') or {}).get('total')
            cpu=row.get('cpu_percent')
            if isinstance(mem,(int,float)) and mem>=90:warnings.append({'type':'memory_pressure','percent':mem,'severity':'HIGH'})
            if isinstance(total,(int,float)) and total>0 and isinstance(free,(int,float)) and free/total<=.10:warnings.append({'type':'disk_capacity','free_percent':free/total*100,'severity':'HIGH'})
            if isinstance(cpu,(int,float)) and cpu>=95:warnings.append({'type':'cpu_saturation','percent':cpu,'severity':'HIGH'})
        cpu_vals=[r.get('cpu_percent') for r in rows if isinstance(r.get('cpu_percent'),(int,float))]
        mem_vals=[(r.get('memory') or {}).get('percent') for r in rows if isinstance((r.get('memory') or {}).get('percent'),(int,float))]
        disk_vals=[]
        for r in rows:
            d=r.get('disk') or {}
            if isinstance(d.get('free'),(int,float)) and isinstance(d.get('total'),(int,float)) and d.get('total'):disk_vals.append(d['free']/d['total']*100)
        return {'status':'SUCCESS','samples':len(rows),'warnings':warnings[-50:],'summary':{'cpu_avg':statistics.fmean(cpu_vals) if cpu_vals else None,'memory_avg':statistics.fmean(mem_vals) if mem_vals else None,'disk_free_percent_latest':disk_vals[-1] if disk_vals else None},'generated_at':time.time()}
