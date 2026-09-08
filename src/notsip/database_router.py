from __future__ import annotations
import os
import re
import sqlite3
from pathlib import Path


_ALLOWED_SOURCES = {'personal', 'documents', 'calendar', 'messages', 'system_logs', 'enterprise', 'analytical'}
_WRITE_RE = re.compile(r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|REINDEX|VACUUM|PRAGMA)\b', re.I)
_MULTI_STMT_RE = re.compile(r';\s*\S')


def _validate_query(query: str) -> str:
    q = str(query or '').strip()
    if not q:
        raise ValueError('query is required')
    if len(q) > 20000:
        raise ValueError('query is too long')
    if '\x00' in q:
        raise ValueError('NUL bytes are not allowed')
    if _MULTI_STMT_RE.search(q.rstrip(';')):
        raise ValueError('multiple SQL statements are not allowed')
    if _WRITE_RE.search(q):
        raise PermissionError('database router is read-only')
    if not re.match(r'^(SELECT|WITH)\b', q, re.I):
        raise PermissionError('database router accepts only SELECT or WITH queries')
    return q.rstrip(';').strip()


def _source_url(source: str) -> str:
    key = f'NOTSIP_{source.upper()}_DATABASE_URL'
    return os.getenv(key, '').strip()


def _sqlite_query(path: Path, query: str, limit: int):
    uri = f'file:{path.resolve()}?mode=ro'
    con = sqlite3.connect(uri, uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute(query)
        rows = [dict(r) for r in cur.fetchmany(limit + 1)]
        truncated = len(rows) > limit
        return rows[:limit], truncated
    finally:
        con.close()


def _postgres_query(url: str, query: str, limit: int):
    try:
        import psycopg
        from psycopg.rows import dict_row
    except Exception as exc:
        raise RuntimeError('PostgreSQL support requires the database optional dependency') from exc
    with psycopg.connect(url, row_factory=dict_row, options='-c default_transaction_read_only=on -c statement_timeout=5000') as con:
        with con.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchmany(limit + 1)
            return [dict(r) for r in rows[:limit]], len(rows) > limit


def query(source: str, query_text: str, limit: int = 100):
    source = str(source or '').strip().lower()
    if source not in _ALLOWED_SOURCES:
        raise ValueError(f'unsupported database source: {source}')
    q = _validate_query(query_text)
    limit = max(1, min(int(limit), 500))
    url = _source_url(source)
    if not url:
        if source in {'personal', 'messages', 'calendar', 'documents'}:
            raise RuntimeError(f'database source {source} is not configured as an external read source')
        raise RuntimeError(f'database source {source} is not configured')
    if url.startswith('sqlite:///'):
        path = Path(url[len('sqlite:///'):]).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        rows, truncated = _sqlite_query(path, q, limit)
    elif url.startswith('postgresql://') or url.startswith('postgres://'):
        rows, truncated = _postgres_query(url, q, limit)
    else:
        raise ValueError('database source must use sqlite:/// or postgresql://')
    return {'status':'SUCCESS','source':source,'rows':rows,'row_count':len(rows),'truncated':truncated,'read_only':True}


def attach(app, require_auth, agent, registry):
    from .policy import Risk
    from .tools import Tool
    from fastapi import Depends
    if registry.get('database_query') is None:
        registry.add(Tool('database_query','Query an explicitly configured read-only NOTSIP database source.','READ_DATABASE',Risk.MEDIUM,{'type':'object','properties':{'source':{'type':'string','enum':sorted(_ALLOWED_SOURCES)},'query':{'type':'string'},'limit':{'type':'integer','minimum':1,'maximum':500}},'required':['source','query']},query))
    from .execution_gate import ToolExecutionGate
    ToolExecutionGate.wrap_registry(registry)
    @app.post('/api/database/query')
    async def database_query(payload:dict,_:None=Depends(require_auth)):
        return await agent.run_tool('database_query',{'source':str(payload.get('source','')),'query':str(payload.get('query','')),'limit':int(payload.get('limit',100) or 100)})
    return registry.get('database_query')
