from pathlib import Path
from tempfile import TemporaryDirectory
from notsip.calendar_service import CalendarStore


def test_calendar_crud_and_conflicts():
    with TemporaryDirectory() as d:
        c=CalendarStore(Path(d),'Africa/Kigali')
        first,conflicts=c.create('A','2026-09-07T10:00:00','2026-09-07T11:00:00')
        assert conflicts==[]
        second,conflicts=c.create('B','2026-09-07T10:30:00','2026-09-07T11:30:00')
        assert conflicts and conflicts[0]['id']==first['id']
        updated,conflicts=c.update(second['id'],title='B2')
        assert updated['title']=='B2'
        assert c.delete(second['id'])['status']=='SUCCESS'
        assert len(c.list())==1
        c2=CalendarStore(Path(d),'Africa/Kigali')
        assert c2.list()[0]['title']=='A'
