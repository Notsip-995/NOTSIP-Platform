from __future__ import annotations
import hashlib,json,os,secrets,sqlite3,threading,time,uuid
from pathlib import Path
from .actor_context import current_actor
class Store:
    def __init__(self,root,database_url=''):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock();self._backend=None
        url=database_url or os.getenv('NOTSIP_DATABASE_URL','')
        if url.startswith('sqlite:///'):self.db=Path(url.replace('sqlite:///','',1));self.db=self.db if self.db.is_absolute() else self.root/self.db.name
        elif url.startswith('postgresql://') or url.startswith('postgres://'):
            from .postgres_store import PostgreSQLStore
            self._backend=PostgreSQLStore(self.root,url);self.db=None;return
        else:self.db=self.root/'notsip.db'
        self.init()
    def conn(self):
        if self._backend:raise RuntimeError('PostgreSQL backend does not expose SQLite connection')
        c=sqlite3.connect(self.db,check_same_thread=False);c.row_factory=sqlite3.Row;return c
    def init(self):
        with self.lock,self.conn() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,role TEXT,content TEXT,ts REAL);CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY,user_id TEXT,kind TEXT,content TEXT,weight REAL,source TEXT,provenance TEXT,ts REAL);CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(content,content='memories',content_rowid='id');CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY,kind TEXT,name TEXT,data TEXT,updated REAL);CREATE TABLE IF NOT EXISTS relations(id INTEGER PRIMARY KEY,subject TEXT,predicate TEXT,object TEXT,confidence REAL,source TEXT,ts REAL);CREATE TABLE IF NOT EXISTS facts(id TEXT PRIMARY KEY,statement TEXT,source TEXT,url TEXT,confidence REAL,retrieved REAL,metadata TEXT);CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,objective TEXT,state TEXT,priority INTEGER,handler TEXT,data TEXT,run_at REAL,interval_sec REAL,retries INTEGER,created REAL,updated REAL,error TEXT,idempotency_key TEXT DEFAULT '');CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,user_id TEXT,request TEXT,interpretation TEXT,tool TEXT,action TEXT,result TEXT,ts REAL);CREATE TABLE IF NOT EXISTS pairing_codes(code TEXT PRIMARY KEY,expires REAL);CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY,name TEXT,platform TEXT,public_key TEXT,token_hash TEXT,last_seen REAL,status TEXT,data TEXT);CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY,device_id TEXT,action TEXT,payload TEXT,status TEXT,created REAL,updated REAL,result TEXT);''')
            cols={r[1] for r in c.execute('PRAGMA table_info(tasks)').fetchall()}
            if 'idempotency_key' not in cols:c.execute("ALTER TABLE tasks ADD COLUMN idempotency_key TEXT DEFAULT ''")
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_idempotency_key ON tasks(idempotency_key) WHERE idempotency_key <> ''")
    def conn_rows(self,sql,args=()):
        with self.lock,self.conn() as c:return [dict(r) for r in c.execute(sql,args).fetchall()]
    def exec(self,sql,args=()):
        if self._backend:return self._backend.exec(sql,args)
        with self.lock,self.conn() as c:c.execute(sql,args)
    def rows(self,sql,args=()):
        if self._backend:return self._backend.rows(sql,args)
        return self.conn_rows(sql,args)
    def row(self,sql,args=()):x=self.rows(sql,args);return x[0] if x else None
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
    def task(self,objective,state='PENDING',priority=0,handler='',data=None,run_at=None,interval_sec=None,idempotency_key=''):
        if self._backend:return self._backend.task(objective,state,priority,handler,data,run_at,interval_sec,idempotency_key)
        tid=str(uuid.uuid4());now=time.time();payload=json.dumps(data or {})
        with self.lock,self.conn() as c:
            try:c.execute('INSERT INTO tasks(id,objective,state,priority,handler,data,run_at,interval_sec,retries,created,updated,error,idempotency_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,objective,state,priority,handler,payload,run_at,interval_sec,0,now,now,'',idempotency_key or ''))
            except sqlite3.IntegrityError:
                if idempotency_key:
                    row=c.execute('SELECT id FROM tasks WHERE idempotency_key=?',(idempotency_key,)).fetchone()
                    if row:return row['id']
                raise
        return tid
    def tasks(self,state=None):
        if self._backend:return self._backend.tasks(state)
        return self.rows(('SELECT * FROM tasks WHERE state=? ORDER BY priority DESC,created ASC' if state else 'SELECT * FROM tasks ORDER BY priority DESC,created ASC'),((state,) if state else ()))
    def claim_task(self,tid,data):
        if self._backend:return self._backend.claim_task(tid,data)
        with self.lock,self.conn() as c:
            cur=c.execute("UPDATE tasks SET state='RUNNING',data=?,error='',updated=? WHERE id=? AND state='PENDING'",(data,time.time(),tid));return cur.rowcount==1
    def task_update(self,tid,**fields):
        if not fields:return
        fields['updated']=time.time();self.exec('UPDATE tasks SET '+','.join(f'{k}=?' for k in fields)+' WHERE id=?',(*fields.values(),tid))
    def restore_runtime_state(self,state):
        if self._backend:return self._backend.restore_runtime_state(state)
        tasks=state.get('tasks') or [];world=state.get('world') or {};devices=state.get('devices') or [];commands=state.get('commands') or []
        with self.lock,self.conn() as c:
            existing_tokens={r['id']:r['token_hash'] for r in c.execute('SELECT id,token_hash FROM devices').fetchall()};c.execute('DELETE FROM commands');c.execute('DELETE FROM tasks');c.execute('DELETE FROM devices');c.execute('DELETE FROM entities');c.execute('DELETE FROM relations');c.execute('DELETE FROM facts')
            for t in tasks:c.execute('INSERT INTO tasks(id,objective,state,priority,handler,data,run_at,interval_sec,retries,created,updated,error,idempotency_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(t.get('id') or str(uuid.uuid4()),t.get('objective',''),t.get('state','PENDING'),int(t.get('priority',0)),t.get('handler','agent'),t.get('data','{}') if isinstance(t.get('data','{}'),str) else json.dumps(t.get('data') or {}),t.get('run_at'),t.get('interval_sec'),int(t.get('retries',0)),float(t.get('created',time.time())),float(t.get('updated',time.time())),t.get('error',''),t.get('idempotency_key','') or ''))
            repair=[]
            for d in devices:
                token_hash=d.get('token_hash') or existing_tokens.get(d.get('id',''),'');status=d.get('status','') if token_hash else 'REPAIR_REQUIRED'
                if not token_hash:repair.append(d.get('id',''))
                data=d.get('data','{}') if isinstance(d.get('data','{}'),str) else json.dumps(d.get('data') or {});c.execute('INSERT INTO devices(id,name,platform,public_key,token_hash,last_seen,status,data) VALUES(?,?,?,?,?,?,?,?)',(d.get('id',''),d.get('name',''),d.get('platform',''),d.get('public_key',''),token_hash,d.get('last_seen'),status,data))
            for cmd in commands:c.execute('INSERT INTO commands(id,device_id,action,payload,status,created,updated,result) VALUES(?,?,?,?,?,?,?,?)',(cmd.get('id') or str(uuid.uuid4()),cmd.get('device_id',''),cmd.get('action',''),cmd.get('payload','{}') if isinstance(cmd.get('payload','{}'),str) else json.dumps(cmd.get('payload') or {}),cmd.get('status','PENDING'),float(cmd.get('created',time.time())),float(cmd.get('updated',time.time())),cmd.get('result','{}') if isinstance(cmd.get('result','{}'),str) else json.dumps(cmd.get('result') or {})))
            for e in world.get('entities') or []:c.execute('INSERT INTO entities(id,kind,name,data,updated) VALUES(?,?,?,?,?)',(e.get('id',''),e.get('kind',''),e.get('name',''),e.get('data','{}') if isinstance(e.get('data','{}'),str) else json.dumps(e.get('data') or {}),float(e.get('updated',time.time()))))
            for r in world.get('relations') or []:c.execute('INSERT INTO relations(id,subject,predicate,object,confidence,source,ts) VALUES(?,?,?,?,?,?,?)',(r.get('id'),r.get('subject',''),r.get('predicate',''),r.get('object',''),float(r.get('confidence',1)),r.get('source','recovery'),float(r.get('ts',time.time()))))
            for f in world.get('facts') or []:c.execute('INSERT INTO facts(id,statement,source,url,confidence,retrieved,metadata) VALUES(?,?,?,?,?,?,?)',(f.get('id') or str(uuid.uuid4()),f.get('statement',''),f.get('source','recovery'),f.get('url',''),float(f.get('confidence',.5)),float(f.get('retrieved',time.time())),f.get('metadata','{}') if isinstance(f.get('metadata','{}'),str) else json.dumps(f.get('metadata') or {})))
        return {'status':'RESTORED','tasks':len(tasks),'devices':len(devices),'commands':len(commands),'devices_requiring_repair':repair,'entities':len(world.get('entities') or []),'relations':len(world.get('relations') or []),'facts':len(world.get('facts') or [])}
    def audit(self,*args):
        if self._backend:return self._backend.audit(*args)
        self.exec('INSERT INTO audit(user_id,request,interpretation,tool,action,result,ts) VALUES(?,?,?,?,?,?,?)',(*args,time.time()))
    def audit_recent(self,n=200):return self._backend.audit_recent(n) if self._backend else self.rows('SELECT * FROM audit ORDER BY id DESC LIMIT ?',(n,))
    def create_pair_code(self,ttl=300):
        if self._backend:return self._backend.create_pair_code(ttl)
        code=secrets.token_urlsafe(8).replace('-','').replace('_','')[:8].upper();self.exec('INSERT OR REPLACE INTO pairing_codes VALUES(?,?)',(code,time.time()+ttl));return code
    def consume_pair_code(self,code):
        if self._backend:return self._backend.consume_pair_code(code)
        with self.lock,self.conn() as c:
            r=c.execute('DELETE FROM pairing_codes WHERE code=? AND expires>? RETURNING code',(code.upper(),time.time())).fetchone();return bool(r)
    def pair_device(self,id,name,platform,public_key,token,owner=None):
        owner=self._owner(owner)
        if self._backend:return self._backend.pair_device(id,name,platform,public_key,token,owner)
        row=self.row('SELECT data FROM devices WHERE id=?',(id,));data=json.loads(row['data'] or '{}') if row else {};data['owner']=owner
        self.exec('INSERT INTO devices(id,name,platform,public_key,token_hash,last_seen,status,data) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,platform=excluded.platform,public_key=excluded.public_key,token_hash=excluded.token_hash,last_seen=excluded.last_seen,status=excluded.status,data=excluded.data',(id,name,platform,public_key,hashlib.sha256(token.encode()).hexdigest(),time.time(),'ONLINE',json.dumps(data)))
    def _owner(self,owner=None):return str(owner or current_actor()).strip() or 'primary-user'
    def device_owner(self,id):
        r=self.row('SELECT data FROM devices WHERE id=?',(id,));
        if not r:return None
        try:return json.loads(r.get('data') or '{}').get('owner','primary-user')
        except Exception:return 'primary-user'
    def device_owned_by(self,id,owner=None):return self.device_owner(id)==self._owner(owner)
    def device_token_valid(self,id,token):
        if self._backend:return self._backend.device_token_valid(id,token)
        r=self.row('SELECT token_hash FROM devices WHERE id=?',(id,));return bool(r and secrets.compare_digest(r['token_hash'],hashlib.sha256(token.encode()).hexdigest()))
    def heartbeat(self,id,status='ONLINE'):
        if self._backend:return self._backend.heartbeat(id,status)
        self.exec('UPDATE devices SET last_seen=?,status=? WHERE id=?',(time.time(),status,id))
    def devices(self,owner=None):
        owner=self._owner(owner);rows=self._backend.devices() if self._backend else self.rows('SELECT id,name,platform,last_seen,status,data FROM devices ORDER BY name');out=[]
        for row in rows:
            try:row_owner=json.loads(row.get('data') or '{}').get('owner','primary-user')
            except Exception:row_owner='primary-user'
            if row_owner==owner:out.append(row)
        return out
    def queue_command(self,device_id,action,payload):return self._backend.queue_command(device_id,action,payload) if self._backend else self._queue_sqlite(device_id,action,payload)
    def _queue_sqlite(self,device_id,action,payload):
        if not self.device_owned_by(device_id):raise PermissionError('device is not owned by current actor')
        cid=str(uuid.uuid4());now=time.time();self.exec('INSERT INTO commands VALUES(?,?,?,?,?,?,?,?)',(cid,device_id,action,json.dumps(payload or {}),'PENDING',now,now,''));return cid
    def pull_commands(self,device_id,limit=20):
        if self._backend:return self._backend.pull_commands(device_id,limit)
        with self.lock,self.conn() as c:
            c.execute('BEGIN IMMEDIATE')
            try:
                rows=[dict(r) for r in c.execute("SELECT * FROM commands WHERE device_id=? AND status='PENDING' ORDER BY created LIMIT ?",(device_id,limit)).fetchall()]
                if rows:ids=[r['id'] for r in rows];c.executemany("UPDATE commands SET status='DELIVERED',updated=? WHERE id=? AND status='PENDING'",[(time.time(),cid) for cid in ids])
                c.commit()
            except Exception:c.rollback();raise
            for r in rows:r['payload']=json.loads(r['payload'])
            return rows
    def command_result(self,cid,status,result,device_id=None):
        if self._backend:return self._backend.command_result(cid,status,result,device_id)
        with self.lock,self.conn() as c:
            if device_id is None:cur=c.execute('UPDATE commands SET status=?,result=?,updated=? WHERE id=?',(status,json.dumps(result),time.time(),cid))
            else:cur=c.execute('UPDATE commands SET status=?,result=?,updated=? WHERE id=? AND device_id=?',(status,json.dumps(result),time.time(),cid,device_id))
            return cur.rowcount==1
