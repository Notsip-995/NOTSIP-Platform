from __future__ import annotations
import hashlib,json,os,secrets,sqlite3,threading,time,uuid
from pathlib import Path
class Store:
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock();self._backend=None
        url=os.getenv('NOTSIP_DATABASE_URL','')
        if url.startswith('postgresql://') or url.startswith('postgres://'):
            from .postgres_store import PostgreSQLStore
            self._backend=PostgreSQLStore(self.root,url);self.db=None;return
        self.db=self.root/'notsip.db';self.init()
    def conn(self):
        if self._backend:raise RuntimeError('PostgreSQL backend does not expose SQLite connection')
        c=sqlite3.connect(self.db,check_same_thread=False);c.row_factory=sqlite3.Row;return c
    def init(self):
        with self.lock,self.conn() as c:c.executescript('''CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,role TEXT,content TEXT,ts REAL);CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY,user_id TEXT,kind TEXT,content TEXT,weight REAL,source TEXT,provenance TEXT,ts REAL);CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(content,content='memories',content_rowid='id');CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY,kind TEXT,name TEXT,data TEXT,updated REAL);CREATE TABLE IF NOT EXISTS relations(id INTEGER PRIMARY KEY,subject TEXT,predicate TEXT,object TEXT,confidence REAL,source TEXT,ts REAL);CREATE TABLE IF NOT EXISTS facts(id TEXT PRIMARY KEY,statement TEXT,source TEXT,url TEXT,confidence REAL,retrieved REAL,metadata TEXT);CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,objective TEXT,state TEXT,priority INTEGER,handler TEXT,data TEXT,run_at REAL,interval_sec REAL,retries INTEGER,created REAL,updated REAL,error TEXT);CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,user_id TEXT,request TEXT,interpretation TEXT,tool TEXT,action TEXT,result TEXT,ts REAL);CREATE TABLE IF NOT EXISTS pairing_codes(code TEXT PRIMARY KEY,expires REAL);CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY,name TEXT,platform TEXT,public_key TEXT,token_hash TEXT,last_seen REAL,status TEXT,data TEXT);CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY,device_id TEXT,action TEXT,payload TEXT,status TEXT,created REAL,updated REAL,result TEXT);''')
    def exec(self,sql,args=()):
        if self._backend:return self._backend.exec(sql,args)
        with self.lock,self.conn() as c:c.execute(sql,args)
    def rows(self,sql,args=()):
        if self._backend:return self._backend.rows(sql,args)
        with self.conn() as c:return [dict(r) for r in c.execute(sql,args).fetchall()]
    def row(self,sql,args=()):
        x=self.rows(sql,args);return x[0] if x else None
    def message(self,role,content):self.exec('INSERT INTO messages(role,content,ts) VALUES(?,?,?)',(role,content,time.time()))
    def history(self,n=24):return self.rows('SELECT role,content FROM messages ORDER BY id DESC LIMIT ?',(n,))[::-1]
    def remember(self,uid,kind,content,weight=.8,source='conversation',provenance=None):
        if self._backend:return self._backend.remember(uid,kind,content,weight,source,provenance)
        with self.lock,self.conn() as c:
            cur=c.execute('INSERT INTO memories(user_id,kind,content,weight,source,provenance,ts) VALUES(?,?,?,?,?,?,?)',(uid,kind,content,weight,source,json.dumps(provenance or {}),time.time()));c.execute('INSERT INTO memory_fts(rowid,content) VALUES(?,?)',(cur.lastrowid,content))
    def memories(self,uid,q='',limit=20):
        if self._backend:return self._backend.memories(uid,q,limit)
        if q:
            try:return self.rows('SELECT m.kind,m.content,m.weight,m.source,m.provenance,m.ts FROM memory_fts f JOIN memories m ON m.id=f.rowid WHERE m.user_id=? AND f.content MATCH ? ORDER BY rank LIMIT ?',(uid,q.replace('"',' '),limit))
            except sqlite3.OperationalError:pass
        return self.rows('SELECT kind,content,weight,source,provenance,ts FROM memories WHERE user_id=? ORDER BY weight DESC,ts DESC LIMIT ?',(uid,limit))
    def entity(self,eid,kind,name,data):
        if self._backend:return self._backend.entity(eid,kind,name,data)
        self.exec('INSERT INTO entities VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET kind=excluded.kind,name=excluded.name,data=excluded.data,updated=excluded.updated',(eid,kind,name,json.dumps(data),time.time()))
    def entities(self):return self._backend.entities() if self._backend else self.rows('SELECT * FROM entities ORDER BY updated DESC')
    def relation(self,s,p,o,confidence=1.,source='system'):
        if self._backend:return self._backend.relation(s,p,o,confidence,source)
        self.exec('INSERT INTO relations(subject,predicate,object,confidence,source,ts) VALUES(?,?,?,?,?,?)',(s,p,o,confidence,source,time.time()))
    def relations(self):return self._backend.relations() if self._backend else self.rows('SELECT * FROM relations ORDER BY ts DESC')
    def fact(self,statement,source,url='',confidence=.5,metadata=None):
        if self._backend:return self._backend.fact(statement,source,url,confidence,metadata)
        fid=str(uuid.uuid4());self.exec('INSERT INTO facts VALUES(?,?,?,?,?,?,?)',(fid,statement,source,url,confidence,time.time(),json.dumps(metadata or {})));return fid
    def facts(self,n=100):return self._backend.facts(n) if self._backend else self.rows('SELECT * FROM facts ORDER BY retrieved DESC LIMIT ?',(n,))
    def task(self,objective,state='PENDING',priority=0,handler='',data=None,run_at=None,interval_sec=None):
        if self._backend:return self._backend.task(objective,state,priority,handler,data,run_at,interval_sec)
        tid=str(uuid.uuid4());now=time.time();self.exec('INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(tid,objective,state,priority,handler,json.dumps(data or {}),run_at,interval_sec,0,now,now,''));return tid
    def tasks(self,state=None):return self._backend.tasks(state) if self._backend else self.rows(('SELECT * FROM tasks WHERE state=? ORDER BY priority DESC,created ASC' if state else 'SELECT * FROM tasks ORDER BY priority DESC,created ASC'),((state,) if state else ()))
    def task_update(self,tid,**fields):
        if not fields:return
        fields['updated']=time.time();self.exec('UPDATE tasks SET '+','.join(f'{k}=?' for k in fields)+' WHERE id=?',(*fields.values(),tid))
    def audit(self,*args):
        if self._backend:return self._backend.audit(*args)
        self.exec('INSERT INTO audit(user_id,request,interpretation,tool,action,result,ts) VALUES(?,?,?,?,?,?,?)',(*args,time.time()))
    def audit_recent(self,n=200):return self._backend.audit_recent(n) if self._backend else self.rows('SELECT * FROM audit ORDER BY id DESC LIMIT ?',(n,))
    def create_pair_code(self,ttl=300):
        if self._backend:return self._backend.create_pair_code(ttl)
        code=secrets.token_urlsafe(8).replace('-','').replace('_','')[:8].upper();self.exec('INSERT OR REPLACE INTO pairing_codes VALUES(?,?)',(code,time.time()+ttl));return code
    def consume_pair_code(self,code):
        if self._backend:return self._backend.consume_pair_code(code)
        r=self.row('SELECT expires FROM pairing_codes WHERE code=?',(code.upper(),));ok=bool(r and r['expires']>time.time());
        if ok:self.exec('DELETE FROM pairing_codes WHERE code=?',(code.upper(),))
        return ok
    def pair_device(self,id,name,platform,public_key,token):
        if self._backend:return self._backend.pair_device(id,name,platform,public_key,token)
        self.exec('INSERT INTO devices(id,name,platform,public_key,token_hash,last_seen,status,data) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,platform=excluded.platform,public_key=excluded.public_key,token_hash=excluded.token_hash,last_seen=excluded.last_seen,status=excluded.status',(id,name,platform,public_key,hashlib.sha256(token.encode()).hexdigest(),time.time(),'ONLINE','{}'))
    def device_token_valid(self,id,token):
        if self._backend:return self._backend.device_token_valid(id,token)
        r=self.row('SELECT token_hash FROM devices WHERE id=?',(id,));return bool(r and secrets.compare_digest(r['token_hash'],hashlib.sha256(token.encode()).hexdigest()))
    def heartbeat(self,id,status='ONLINE'):
        if self._backend:return self._backend.heartbeat(id,status)
        self.exec('UPDATE devices SET last_seen=?,status=? WHERE id=?',(time.time(),status,id))
    def devices(self):return self._backend.devices() if self._backend else self.rows('SELECT id,name,platform,last_seen,status,data FROM devices ORDER BY name')
    def queue_command(self,device_id,action,payload):return self._backend.queue_command(device_id,action,payload) if self._backend else self._queue_sqlite(device_id,action,payload)
    def _queue_sqlite(self,device_id,action,payload):
        cid=str(uuid.uuid4());now=time.time();self.exec('INSERT INTO commands VALUES(?,?,?,?,?,?,?,?)',(cid,device_id,action,json.dumps(payload or {}),'PENDING',now,now,''));return cid
    def pull_commands(self,device_id,limit=20):
        if self._backend:return self._backend.pull_commands(device_id,limit)
        rows=self.rows("SELECT * FROM commands WHERE device_id=? AND status='PENDING' ORDER BY created LIMIT ?",(device_id,limit))
        for r in rows:self.exec('UPDATE commands SET status=?,updated=? WHERE id=?',('DELIVERED',time.time(),r['id']));r['payload']=json.loads(r['payload'])
        return rows
    def command_result(self,cid,status,result):
        if self._backend:return self._backend.command_result(cid,status,result)
        self.exec('UPDATE commands SET status=?,result=?,updated=? WHERE id=?',(status,json.dumps(result),time.time(),cid))
