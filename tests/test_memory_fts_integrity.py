from pathlib import Path


def test_sqlite_fts_fallback_is_limited_to_query_syntax_errors():
    source=Path('src/notsip/store.py').read_text(encoding='utf-8')
    assert "except sqlite3.OperationalError as exc:" in source
    assert "'malformed match expression'" in source
    assert "and 'syntax error' not in str(exc).lower():raise" in source
