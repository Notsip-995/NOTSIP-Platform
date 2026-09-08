import asyncio
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from notsip.agent import Agent
from notsip.calendar_service import CalendarStore, attach
from notsip.policy import Policy
from notsip.tools import Registry
from notsip.store import Store
from notsip.world import WorldModel
from notsip.config import settings


def test_calendar_store_detects_conflict_and_persists(tmp_path):
    c=CalendarStore(tmp_path,'Africa/Kigali')
    event,conflicts=c.create('Meeting','2026-09-10T10:00:00+02:00','2026-09-10T11:00:00+02:00')
    assert conflicts==[]
    _,conflicts=c.create('Overlap','2026-09-10T10:30:00+02:00','2026-09-10T11:30:00+02:00')
    assert conflicts and conflicts[0]['id']==event['id']
    assert len(CalendarStore(tmp_path,'Africa/Kigali').list())==2


def test_calendar_mutation_requires_write_calendar_capability(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'data_dir',str(tmp_path));monkeypatch.setattr(settings,'autonomy_level',1);monkeypatch.setattr(settings,'capability_levels',{'WRITE_CALENDAR':2})
    store=Store(tmp_path);registry=Registry()
    agent=Agent(settings,store,Policy(1),registry,SimpleNamespace(enabled=False,fallback_enabled=False),WorldModel(store))
    decision=agent.policy.decide(1,False,'WRITE_CALENDAR')
    assert decision.allowed is False
    assert decision.needs_confirmation is True


def test_calendar_http_mutation_fails_closed_without_agent(tmp_path):
    app=FastAPI();attach(app,lambda:None,tmp_path,'Africa/Kigali',agent=None,registry=None)
    client=TestClient(app)
    response=client.post('/api/calendar/events',json={'title':'Blocked','start':'2026-09-10T10:00:00+02:00','end':'2026-09-10T11:00:00+02:00'})
    assert response.status_code==503
    assert CalendarStore(tmp_path,'Africa/Kigali').list()==[]
