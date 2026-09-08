import asyncio
from types import SimpleNamespace
from notsip.agent import Agent
from notsip.calendar_service import CalendarStore
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
    agent=Agent(settings,Store(tmp_path),Policy(1),Registry(),SimpleNamespace(enabled=False,fallback_enabled=False),WorldModel(Store(tmp_path)))
    result=asyncio.run(agent.run_tool('calendar_create',{'title':'x','start':'2026-09-10T10:00:00+02:00','end':'2026-09-10T11:00:00+02:00'}))
    assert result['status']=='FAILURE'
    assert result['approval_required'] is True
