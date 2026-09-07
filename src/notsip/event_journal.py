from __future__ import annotations
import json, threading, time
from pathlib import Path

class EventJournal:
    def __init__(self, root, max_events=20000):
        self.path=Path(root)/'runtime'/'events.jsonl';self.path.parent.mkdir(parents=True,exist_ok=True);self.max_events=max(1000,int(max_events));self.lock=threading.RLock()
    def append(self,event):
        row={'ts':time.time(),'type':event.type,'source':event.source,'timestamp':event.timestamp,'payload':event.payload}
        with self.lock,self.path.open('a',encoding='utf-8') as f:f.write(json.dumps(row,sort_keys=True,default=str)+'\n')
        self._trim();return row
    def _trim(self):
        try:
            lines=self.path.read_text(encoding='utf-8').splitlines()
            if len(lines)>self.max_events:self.path.write_text('\n'.join(lines[-self.max_events:])+'\n',encoding='utf-8')
        except Exception:pass
    def recent(self,limit=500):
        if not self.path.exists():return []
        rows=[]
        for line in self.path.read_text(encoding='utf-8').splitlines()[-max(1,min(int(limit),5000)):]:
            try:rows.append(json.loads(line))
            except Exception:continue
        return rows

class JournaledEventBus:
    def __init__(self,bus,journal):self.bus=bus;self.journal=journal
    async def publish(self,event):
        row=self.journal.append(event)
        errors=await self.bus.publish(event)
        if errors:row['handler_errors']=errors
        return errors
