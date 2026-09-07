from pathlib import Path
from tempfile import TemporaryDirectory
from notsip.calendar_service import CalendarStore
from notsip.event_journal import EventJournal
from notsip.event_reconstruction import EventReconstructor
from notsip.health_analytics import HealthAnalytics
from notsip.events import Event


def test_event_journal_round_trip():
    with TemporaryDirectory() as d:
        j=EventJournal(Path(d),max_events=10);j.append(Event('test',{'value':1},'unit'))
        rows=j.recent()
        assert rows and rows[0]['type']=='test' and rows[0]['payload']['value']==1


def test_event_reconstruction_uses_journal():
    with TemporaryDirectory() as d:
        j=EventJournal(Path(d));j.append(Event('alpha',{'x':1},'unit'))
        class S:
            def audit_recent(self,n=200): return []
        result=EventReconstructor(S(),j).reconstruct()
        assert result['events'] and result['counts']['alpha']==1


def test_calendar_conflict_and_persistence():
    with TemporaryDirectory() as d:
        c=CalendarStore(Path(d),'Africa/Kigali')
        a,_=c.create('A','2026-09-07T10:00:00','2026-09-07T11:00:00')
        b,conflicts=c.create('B','2026-09-07T10:30:00','2026-09-07T11:30:00')
        assert conflicts and conflicts[0]['id']==a['id']
        assert c.delete(b['id'])['status']=='SUCCESS'
        assert CalendarStore(Path(d),'Africa/Kigali').list()[0]['id']==a['id']


def test_health_analytics_warns_on_pressure():
    with TemporaryDirectory() as d:
        h=HealthAnalytics(Path(d));h.record({'cpu_percent':99,'memory':{'percent':95},'disk':{'free':5,'total':100}})
        out=h.analyze()
        kinds={x['type'] for x in out['warnings']}
        assert {'cpu_saturation','memory_pressure','disk_capacity'} <= kinds
