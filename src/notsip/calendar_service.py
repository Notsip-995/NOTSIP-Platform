from __future__ import annotations
import json, time, uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from fastapi import Depends, HTTPException
from .policy import Risk
from .tools import Tool
from .execution_gate import ToolExecutionGate

class CalendarStore:
    def __init__(self,root,timezone):
        self.path=Path(root)/'calendar.json';self.timezone=timezone;self.path.parent.mkdir(parents=True,exist_ok=True);self.events=[];self.load()
    def load(self):
        try:self.events=json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else []
        except Exception:self.events=[]
        return self.events
    def save(self):
        tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(self.events,indent=2,sort_keys=True),encoding='utf-8');tmp.replace(self.path)
    def _parse(self,value):
        if isinstance(value,(int,float)):return float(value)
        dt=datetime.fromisoformat(str(value).strip().replace('Z','+00:00'))
        if dt.tzinfo is None:dt=dt.replace(tzinfo=ZoneInfo(self.timezone))
        return dt.timestamp()
    def conflicts(self,start,end,exclude=''):return [e for e in self.events if e.get('id')!=exclude and e.get('start_ts',0)<end and e.get('end_ts',0)>start]
    def create(self,title,start,end,description='',location='',reminder_minutes=15):
        st,en=self._parse(start),self._parse(end)
        if en<=st:raise ValueError('end must be after start')
        conflicts=self.conflicts(st,en);event={'id':str(uuid.uuid4()),'title':title,'description':description,'location':location,'start':start,'end':end,'start_ts':st,'end_ts':en,'reminder_minutes':int(reminder_minutes),'created_at':time.time(),'updated_at':time.time()};self.events.append(event);self.save();return event,conflicts
    def update(self,eid,**changes):
        item=next((e for e in self.events if e.get('id')==eid),None)
        if not item:raise KeyError(eid)
        allowed={'title','description','location','start','end','reminder_minutes'};changes={k:v for k,v in changes.items() if k in allowed};start=changes.get('start',item['start']);end=changes.get('end',item['end']);st,en=self._parse(start),self._parse(end)
        if en<=st:raise ValueError('end must be after start')
        conflicts=self.conflicts(st,en,eid);item.update(changes);item['start_ts']=st;item['end_ts']=en;item['updated_at']=time.time();self.save();return item,conflicts
    def delete(self,eid):
        before=len(self.events);self.events=[e for e in self.events if e.get('id')!=eid]
        if len(self.events)==before:raise KeyError(eid)
        self.save();return {'status':'SUCCESS','deleted':eid}
    def list(self,start=None,end=None):
        self.load();items=self.events
        if start is not None:
            st=self._parse(start);items=[e for e in items if e['end_ts']>=st]
        if end is not None:
            en=self._parse(end);items=[e for e in items if e['start_ts']<=en]
        return sorted(items,key=lambda e:e['start_ts'])

def attach(app,require_auth,root,timezone,agent=None,registry=None):
    store=CalendarStore(root,timezone)
    async def create_tool(title,start,end,description='',location='',reminder_minutes=15):
        event,conflicts=store.create(title,start,end,description,location,reminder_minutes);return {'status':'SUCCESS','event':event,'conflicts':conflicts,'conflict':bool(conflicts)}
    async def update_tool(event_id,**changes):
        event,conflicts=store.update(event_id,**changes);return {'status':'SUCCESS','event':event,'conflicts':conflicts,'conflict':bool(conflicts)}
    async def delete_tool(event_id):return store.delete(event_id)
    if registry is not None:
        registry.add(Tool('calendar_create','Create an authorized calendar event and report conflicts.','WRITE_CALENDAR',Risk.MEDIUM,{'type':'object','properties':{'title':{'type':'string'},'start':{'type':'string'},'end':{'type':'string'},'description':{'type':'string'},'location':{'type':'string'},'reminder_minutes':{'type':'integer'}},'required':['title','start','end']},create_tool))
        registry.add(Tool('calendar_update','Modify an authorized calendar event and report conflicts.','WRITE_CALENDAR',Risk.MEDIUM,{'type':'object','properties':{'event_id':{'type':'string'},'title':{'type':'string'},'start':{'type':'string'},'end':{'type':'string'},'description':{'type':'string'},'location':{'type':'string'},'reminder_minutes':{'type':'integer'}},'required':['event_id']},update_tool))
        registry.add(Tool('calendar_delete','Delete an authorized calendar event; confirmation is required.','WRITE_CALENDAR',Risk.HIGH,{'type':'object','properties':{'event_id':{'type':'string'}},'required':['event_id']},delete_tool,True));ToolExecutionGate.wrap_registry(registry)
    @app.get('/api/calendar/events')
    async def calendar_list(start:str='',end:str',_:None=Depends(require_auth)):return {'events':store.list(start or None,end or None)}
    def require_agent():
        if agent is None:raise HTTPException(503,'calendar mutation service is not configured')
    @app.post('/api/calendar/events')
    async def calendar_create(payload:dict,_:None=Depends(require_auth)):
        require_agent()
        return await agent.run_tool('calendar_create',{'title':str(payload.get('title','')).strip(),'start':payload.get('start'),'end':payload.get('end'),'description':str(payload.get('description','')),'location':str(payload.get('location','')),'reminder_minutes':int(payload.get('reminder_minutes',15))})
    @app.patch('/api/calendar/events/{event_id}')
    async def calendar_update(event_id:str,payload:dict,_:None=Depends(require_auth)):
        require_agent()
        return await agent.run_tool('calendar_update',dict(payload,event_id=event_id))
    @app.delete('/api/calendar/events/{event_id}')
    async def calendar_delete(event_id:str,_:None=Depends(require_auth)):
        require_agent()
        return await agent.run_tool('calendar_delete',{'event_id':event_id})
    return store
