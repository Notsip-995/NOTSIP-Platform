import sqlite3


def test_database_router_rejects_writes():
    from notsip.database_router import _validate_query
    try:
        _validate_query('UPDATE users SET name = 1')
    except PermissionError:
        pass
    else:
        raise AssertionError('write query was accepted')


def test_database_router_reads_sqlite_without_mutation(monkeypatch, tmp_path):
    db = tmp_path / 'source.db'
    con = sqlite3.connect(db)
    con.execute('CREATE TABLE items(id INTEGER PRIMARY KEY, value TEXT)')
    con.execute('INSERT INTO items(value) VALUES (?)', ('alpha',))
    con.commit()
    con.close()
    monkeypatch.setenv('NOTSIP_ANALYTICAL_DATABASE_URL', f'sqlite:///{db}')
    from notsip.database_router import query
    result = query('analytical', 'SELECT value FROM items', 10)
    assert result['status'] == 'SUCCESS'
    assert result['read_only'] is True
    assert result['rows'] == [{'value': 'alpha'}]


def test_database_router_rejects_multiple_statements():
    from notsip.database_router import _validate_query
    try:
        _validate_query('SELECT 1; SELECT 2')
    except ValueError:
        pass
    else:
        raise AssertionError('multiple statements were accepted')
