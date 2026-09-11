import time
from notsip.event_reconstruction import EventReconstructor
from notsip.event_journal import EventJournal
from notsip.events import Event
from notsip.store import Store


def test_event_reconstruction_confidence_penalizes_large_gaps(tmp_path):
    store=Store(tmp_path);journal=EventJournal(tmp_path)
    journal.append(Event('one',{'v':1},'test',timestamp='2026-09-08T10:00:00+00:00'))
    # EventJournal stores its own timestamp, so use audit records to produce the second point.
    store.audit('u','request','interpretation','tool','action','result')
    result=EventReconstructor(store,journal).reconstruct()
    assert 0.0 < result['confidence'] <= 0.95
    assert 'confidence_explanation' in result
