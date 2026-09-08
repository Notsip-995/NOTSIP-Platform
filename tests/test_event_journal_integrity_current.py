from pathlib import Path


def test_event_journal_does_not_silently_discard_corrupt_records():
    text=Path('src/notsip/event_journal.py').read_text(encoding='utf-8')
    assert "event journal contains" in text
    assert "JSONDecodeError" in text
    assert "tmp=self.path.with_suffix('.tmp')" in text
