from notsip.event_journal import EventJournal
from notsip.events import Event


def test_event_journal_redacts_sensitive_payload_fields(tmp_path):
    journal=EventJournal(tmp_path)
    journal.append(Event('integration.result',{'token':'VALUE_A','nested':{'client_secret':'VALUE_B','safe':'value'},'items':[{'access_token':'VALUE_C'}]},'test'))
    text=(tmp_path/'runtime'/'events.jsonl').read_text()
    assert 'VALUE_A' not in text
    assert 'VALUE_B' not in text
    assert 'VALUE_C' not in text
    assert '"safe": "value"' in text
