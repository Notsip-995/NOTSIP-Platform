from __future__ import annotations
import json,threading,time
from pathlib import Path

_SENSITIVE={'password','passwd','secret','token','api_key','access_token','refresh_token','client_secret','authorization','cookie','set-cookie','device_token','event_hmac_secret','pairing_secret','node_shared_secret'}

def _redact(value):
    if isinstance(value,dict):
        return {str(k):('[REDACTED]' if str(k).lower().replace('-','_') in _SENSITIVE or any(part in str(k).lower() for part in ('password','secret','token')) else _redact(v)) for k,v in value.items()}
    if isinstance(value,list):return [_redact(v) for v in value]
    if isinstance(value,tuple):return [_redact(v) for v in value]
    return value

class EventJournal:
    def __init__(self, root, max_events=20000):
        self.path=Path(root)/'runtime'/'events.jsonl';self.path.parent.mkdir(parents=True,exist_ok=True);self.max_events=max(1000,int(max_events));self.lock=threading.RLock()
    def append(self,event):
        row={'ts':time.time(),'type':event.type,'source':event.source,'timestamp':event.timestamp,'payload':_redact(event.payload)}
        with self.lock,self.path.open('a',encoding='utf-8') as f:f.write(json.dumps(row,sort_keys=True,default=str)+'\n')
        trimmed=self._trim()
        if trimmed.get('status')!='SUCCESS':row['maintenance_warning']=trimmed
        return row
    def _trim(self):
        with self.lock:
            lines=self.path.read_text(encoding='utf-8').splitlines()
            if len(lines)<=self.max_events:return {'status':'SUCCESS','trimmed':0}
            kept=lines[-self.max_events:]
            tmp=self.path.with_suffix('.tmp');tmp.write_text('\n'.join(kept)+'\n',encoding='utf-8');tmp.replace(self.path)
            return {'status':'SUCCESS','trimmed':len(lines)-len(kept)}
    def recent(self,limit=500):
        if not self.path.exists():return []
        rows=[];bad=0
        for line in self.path.read_text(encoding='utf-8').splitlines()[-max(1,min(int(limit),5000)):]:
            try:rows.append(json.loads(line))
            except json.JSONDecodeError:bad+=1
        if bad:raise RuntimeError(f'event journal contains {bad} malformed record(s)')
        return rows

class JournaledEventBus:
    def __init__(self,bus,journal):self.bus=bus;self.journal=journal
    async def publish(self,event):
        row=self.journal.append(event)
        errors=await self.bus.publish(event)
        if errors:row['handler_errors']=errors
        return errors
