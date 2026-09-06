from __future__ import annotations
import json, sqlite3, time, threading
from pathlib import Path
class Store:
    def __init__(self,data_dir:str): self.root=Path(data_dir); self.root.mkdir(parents=True,exist_ok=True); self.db=self.root/'notsip.db'; self.lock=threading.Lock(); self._init()
    def _conn(self): c=sqlite3.connect(self.db); c.row_factory=sqlite3.Row; return c
    def _init(self):
        with self.lock, self._conn() as c: c.executescript('''CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, role TEXT, content TEXT, ts REAL); CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY, user_id TEXT, kind TEXT, content TEXT, weight REAL, ts REAL); CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY, kind TEXT, name TEXT, data TEXT, updated REAL); CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, objective TEXT, state TEXT, priority INTEGER, data TEXT, updated REAL); CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, user_id TEXT, request TEXT, interpretation TEXT, tool TEXT, action TEXT, result TEXT, ts REAL); CREATE TABLE IF NOT EXISTS paired_devices(id TEXT PRIMARY KEY, name TEXT, platform TEXT, public_key TEXT, last_seen REAL, status TEXT, data TEXT, token_hash TEXT);''')
    def add_message(self,role,content):
        with self.lock, self._conn() as c: c.execute('INSERT INTO messages(role,content,ts) VALUES(?,?,?)',(role,content,time.time()))
    def recent_messages(self,n=20):
        with self._conn() as c: return [dict(r) for r in c.execute('SELECT role,content FROM messages ORDER BY id DESC LIMIT ?', (n,)).fetchall()][::-1]
    def remember(self,user_id,kind,content,weight=.8):
        with self.lock, self._conn() as c: c.execute('INSERT INTO memories(user_id,kind,content,weight,ts) VALUES(?,?,?,?,?)',(user_id,kind,content,weight,time.time()))
    def search_memory(self,user_id,q,limit=20):
        like=f'%{q}%'; sql='SELECT kind,content,weight,ts FROM memories WHERE user_id=? AND content LIKE ? ORDER BY weight DESC, ts DESC LIMIT ?'
        with self._conn() as c: return [dict(r) for r in c.execute(sql,(user_id,like,limit)).fetchall()]
    def upsert_entity(self,eid,kind,name,data):
        with self.lock, self._conn() as c: c.execute('INSERT INTO entities(id,kind,name,data,updated) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET kind=excluded.kind,name=excluded.name,data=excluded.data,updated=excluded.updated',(eid,kind,name,json.dumps(data),time.time()))
    def list_entities(self,kind=None):
        sql='SELECT id,kind,name,data,updated FROM entities'; args=()
        if kind: sql+=' WHERE kind=?'; args=(kind,)
        with self._conn() as c: return [{**dict(r),'data':json.loads(r['data'])} for r in c.execute(sql,args).fetchall()]
    def put_task(self,tid,objective,state='PENDING',priority=0,data=None):
        with self.lock, self._conn() as c: c.execute('INSERT INTO tasks(id,objective,state,priority,data,updated) VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET objective=excluded.objective,state=excluded.state,priority=excluded.priority,data=excluded.data,updated=excluded.updated',(tid,objective,state,priority,json.dumps(data or {}),time.time()))
    def list_tasks(self,state=None):
        sql='SELECT id,objective,state,priority,data,updated FROM tasks'; args=()
        if state: sql+=' WHERE state=?'; args=(state,)
        with self._conn() as c: return [{**dict(r),'data':json.loads(r['data'])} for r in c.execute(sql,args).fetchall()]
    def audit(self,user_id,request,interpretation,tool,action,result):
        with self.lock, self._conn() as c: c.execute('INSERT INTO audit(user_id,request,interpretation,tool,action,result,ts) VALUES(?,?,?,?,?,?,?)',(user_id,request,interpretation,tool,action,result,time.time()))
    def recent_audit(self,n=100):
        with self._conn() as c: return [dict(r) for r in c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT ?', (n,)).fetchall()]
    def pair_device(self,id,name,platform,public_key,token_hash,data=None):
        with self.lock, self._conn() as c: c.execute('INSERT INTO paired_devices(id,name,platform,public_key,last_seen,status,data,token_hash) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,platform=excluded.platform,public_key=excluded.public_key,last_seen=excluded.last_seen,status=excluded.status,data=excluded.data,token_hash=excluded.token_hash',(id,name,platform,public_key,time.time(),'ONLINE',json.dumps(data or {}),token_hash))
    def heartbeat(self,id,status='ONLINE'):
        with self.lock, self._conn() as c: c.execute('UPDATE paired_devices SET last_seen=?,status=? WHERE id=?',(time.time(),status,id))
    def device_token_hash(self,id):
        with self._conn() as c:
            row=c.execute('SELECT token_hash FROM paired_devices WHERE id=?',(id,)).fetchone(); return row['token_hash'] if row else None
    def devices(self):
        with self._conn() as c: return [dict(r) for r in c.execute('SELECT * FROM paired_devices ORDER BY name').fetchall()]
