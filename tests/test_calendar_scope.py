from notsip.calendar_service import CalendarStore


def test_calendar_files_are_actor_scoped(tmp_path):
    a = CalendarStore(tmp_path, 'UTC', 'actor-a')
    b = CalendarStore(tmp_path, 'UTC', 'actor-b')
    a.create('A', '2030-01-01T10:00:00Z', '2030-01-01T11:00:00Z')
    b.create('B', '2030-01-01T10:00:00Z', '2030-01-01T11:00:00Z')
    assert [x['title'] for x in a.list()] == ['A']
    assert [x['title'] for x in b.list()] == ['B']
    assert a.path != b.path
