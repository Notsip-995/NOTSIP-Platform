from __future__ import annotations
import hashlib,json,secrets,time,uuid
from contextlib import contextmanager
from .actor_context import current_actor
try:
    import psycopg
    from psycopg.rows import dict_row
except Exception:psycopg=None;dict_row=None

class PostgreSQLStore:
    def __init__(self,root,url):
        if psycopg is None:raise RuntimeError('PostgreSQL mode requires psycopg[binary]')
        self.root=root;self.url=url;self.init()
    @contextmanager
    def conn(self):
        with psycopg.connect(self.url,row_factory=dict_row) as c:yield c
    def init(self):
        sql='''CREATE TABLE IF NOT EXISTS messages(id BIGSERIAL PRIMARY KEY,role TEXT,content TEXT,ts DOUBLE PRECISION);CREATE TABLE IF NOT EXISTS memories(id BIGSERIAL PRIMARY KEY,user_id TEXT,kind TEXT,content TEXT,weight DOUBLE PRECISION,source TEXT,provenance TEXT,ts DOUBLE PRECISION);'''
        with self.conn() as c:
            c.execute(sql);c.execute('CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY,kind TEXT,name TEXT,data TEXT,updated DOUBLE PRECISION)');c.execute('CREATE TABLE IF NOT EXISTS relations(id BIGSERIAL PRIMARY KEY,subject TEXT,predicate TEXT,object TEXT,confidence DOUBLE PRECISION,source TEXT,ts DOUBLE PRECISION)');c.execute('CREATE TABLE IF NOT EXISTS facts(id TEXT PRIMARY KEY,statement TEXT,source TEXT,url TEXT,confidence DOUBLE PRECISION,retrieved DOUBLE PRECISION,metadata TEXT)');c.execute('CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,objective TEXT,state TEXT,priority INTEGER,handler TEXT,data TEXT,run_at DOUBLE PRECISION,interval_sec DOUBLE PRECISION,retries INTEGER,created DOUBLE PRECISION,updated DOUBLE PRECISION,error TEXT,idempotency_key TEXT DEFAULT \'\')');c.execute('CREATE TABLE IF NOT EXISTS audit(id BIGSERIAL PRIMARY KEY,user_id TEXT,request TEXT,interpretation TEXT,tool TEXT,action TEXT,result TEXT,ts DOUBLE PRECISION)');c.execute('CREATE TABLE IF NOT EXISTS pairing_codes(code TEXT PRIMARY KEY,expires DOUBLE PRECISION)');c.execute('CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY,name TEXT,platform TEXT,public_key TEXT,token_hash TEXT,last_seen DOUBLE PRECISION,status TEXT,data TEXT)');c.execute('CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY,device_id TEXT,action TEXT,payload TEXT,status TEXT,created DOUBLE PRECISION,updated DOUBLE PRECISION,result TEXT)');c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_idempotency_key ON tasks(idempotency_key) WHERE idempotency_key <> ''");c.commit()
    def exec(self,sql,args=()):
        q=sql.replace('INSERT OR REPLACE','INSERT').replace('?','%s')
        with self.conn() as c:c.execute(q,args);c.commit()
    def rows(self,sql,args=()):
        with self.conn() as c:c.execute(sql.replace('?','%s'),args);return c.fetchall()
    def row(self,sql,args=()):r=self.rows(sql,args);return r[0] if r else None
    def message(self,role,content):self.exec('INSERT INTO messages(role,content,ts) VALUES(%s,%s,%s)',(role,content,time.time()))
    def history(self,n=24):return list(reversed(self.rows('SELECT role,content FROM messages ORDER BY id DESC LIMIT %s',(n,))))
    def remember(self,uid,kind,content,weight=.8,source='conversation',provenance=None):self.exec('INSERT INTO memories(user_id,kind,content,weight,source,provenance,ts) VALUES(%s,%s,%s,%s,%s,%s,%s)',(uid,kind,content,weight,source,json.dumps(provenance or {}),time.time()))
    def memories(self,uid,q='',limit=20):return self.rows('SELECT kind,content,weight,source,provenance,ts FROM memories WHERE user_id=%s '+('AND content ILIKE %s ' if q else '')+'ORDER BY weight DESC,ts DESC LIMIT %s',((uid,'%'+q+'%',limit) if q else (uid,limit)))
    def entity(self,eid,kind,name,data):self.exec('INSERT INTO entities(id,kind,name,data,updated) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET kind=EXCLUDED.kind,name=EXCLUDED.name,data=EXCLUDED.data,updated=EXCLUDED.updated',(eid,kind,name,json.dumps(data),time.time()))
    def entities(self):return self.rows('SELECT * FROM entities ORDER BY updated DESC')
    def relation(self,s,p,o,confidence=1.,source='system'):self.exec('INSERT INTO relations(subject,predicate,object,confidence,source,ts) VALUES(%s,%s,%s,%s,%s,%s)',(s,p,o,confidence,source,time.time()))
    def relations(self):return self.rows('SELECT * FROM relations ORDER BY ts DESC')
    def fact(self,statement,source,url='',confidence=.5,metadata=None):fid=str(uuid.uuid4());self.exec('INSERT INTO facts(id,statement,source,url,confidence,retrieved,metadata) VALUES(%s,%s,%s,%s,%s,%s,%s)',(fid,statement,source,url,confidence,time.time(),json.dumps(metadata or {})));return fid
    def facts(self,n=100):return self.rows('SELECT * FROM facts ORDER BY retrieved DESC LIMIT %s',(n,))
    def task(self,objective,state='PENDING',priority=0,handler='',data=None,run_at=None,interval_sec=None,idempotency_key=''):
        tid=str(uuid.uuid4());now=time.time();payload=json.dumps(data or {})
        with self.conn() as c:
            if idempotency_key:
                row=c.execute('INSERT INTO tasks(id,objective,state,priority,handler,data,run_at,interval_sec,retries,created,updated,error,idempotency_key) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id',(tid,objective,state,priority,handler,payload,run_at,interval_sec,0,now,now,'',idempotency_key)).fetchone();
                if row:c.commit();return row['id']
                existing=c.execute('SELECT id FROM tasks WHERE idempotency_key=%s',(idempotency_key,)).fetchone();c.commit();return existing['id'] if existing else None
            row=c.execute('INSERT INTO tasks(id,objective,state,priority,handler,data,run_at,interval_sec,retries,created,updated,error,idempotency_key) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id',(tid,objective,state,priority,handler,payload,run_at,interval_sec,0,now,now,'','')).fetchone();c.commit();return row['id']
    def tasks(self,state=None):q='SELECT * FROM tasks'+(' WHERE state=%s' if state else '')+' ORDER BY priority DESC,created ASC';return self.rows(q,(state,) if state else ())
    def claim_task(self,tid,data):
        with self.conn() as c:row=c.execute("UPDATE tasks SET state='RUNNING',data=%s,error='',updated=%s WHERE id=%s AND state='PENDING' RETURNING id",(data,time.time(),tid)).fetchone();c.commit();return bool(row)
    def task_update(self,tid,**fields):
        if not fields:return
        fields['updated']=time.time();cols=','.join(f'{k}=%s' for k in fields);self.exec(f'UPDATE tasks SET {cols} WHERE id=%s',(*fields.values(),tid))
    def restore_runtime_state(self,state):return {'status':'RESTORE_NOT_IMPLEMENTED'}
    def audit(self,*args):self.exec('INSERT INTO audit(user_id,request,interpretation,tool,action,result,ts) VALUES(%s,%s,%s,%s,%s,%s,%s)',(*args,time.time()))
    def audit_recent(self,n=200):return self.rows('SELECT * FROM audit ORDER BY id DESC LIMIT %s',(n,))
    def create_pair_code(self,ttl=300):code=secrets.token_urlsafe(8).replace('-','').replace('_','')[:8].upper();self.exec('INSERT INTO pairing_codes(code,expires) VALUES(%s,%s) ON CONFLICT(code) DO UPDATE SET expires=EXCLUDED.expires',(code,time.time()+ttl));return code
    def consume_pair_code(self,code):
        with self.conn() as c:r=c.execute('DELETE FROM pairing_codes WHERE code=%s AND expires>%s RETURNING code',(code.upper(),time.time())).fetchone();c.commit();return bool(r)
    def _owner(self,owner=None):return str(owner or current_actor()).strip() or 'primary-user'
    def pair_device(self,id,name,platform,public_key,token,owner=None):owner=self._owner(owner);existing=self.row('SELECT data FROM devices WHERE id=%s',(id,));data=json.loads(existing['data'] or '{}') if existing else {};data['owner']=owner;self.exec('INSERT INTO devices(id,name,platform,public_key,token_hash,last_seen,status,data) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET name=EXCLUDED.name,platform=EXCLUDED.platform,public_key=EXCLUDED.public_key,token_hash=EXCLUDED.token_hash,last_seen=EXCLUDED.last_seen,status=EXCLUDED.status,data=EXCLUDED.data',(id,name,platform,public_key,hashlib.sha256(token.encode()).hexdigest(),time.time(),'ONLINE',json.dumps(data)))
    def device_owner(self,id):r=self.row('SELECT data FROM devices WHERE id=%s',(id,));
        # unreachable indentation kept canonical formatting in source generator
