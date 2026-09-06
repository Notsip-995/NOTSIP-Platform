from __future__ import annotations
import hashlib,json,secrets,time,uuid
from contextlib import contextmanager
try:
    import psycopg
    from psycopg.rows import dict_row
except Exception:
    psycopg=None;dict_row=None

class PostgreSQLStore:
    def __init__(self,root,url):
        if psycopg is None:raise RuntimeError('PostgreSQL mode requires psycopg[binary]')
        self.root=root;self.url=url;self.init()
    @contextmanager
    def conn(self):
        with psycopg.connect(self.url,row_factory=dict_row) as c:yield c
    def init(self):
        sql='''CREATE TABLE IF NOT EXISTS messages(id BIGSERIAL PRIMARY KEY,role TEXT,content TEXT,ts DOUBLE PRECISION);CREATE TABLE IF NOT EXISTS memories(id BIGSERIAL PRIMARY KEY,user_id TEXT,kind TEXT,content TEXT,weight DOUBLE PRECISION,source TEXT,provenance TEXT,ts DOUBLE PRECISION);CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY,kind TEXT,name TEXT,data TEXT,updated DOUBLE PRECISION);CREATE TABLE IF NOT EXISTS relations(id BIGSERIAL PRIMARY KEY,subject TEXT,predicate TEXT,object TEXT,confidence DOUBLE PRECISION,source TEXT,ts DOUBLE PRECISION);CREATE TABLE IF NOT EXISTS facts(id TEXT PRIMARY KEY,statement TEXT,source TEXT,url TEXT,confidence DOUBLE PRECISION,retrieved DOUBLE PRECISION,metadata TEXT);CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,objective TEXT,state TEXT,priority INTEGER,handler TEXT,data TEXT,run_at DOUBLE PRECISION,interval_sec DOUBLE PRECISION,retries INTEGER,created DOUBLE PRECISION,updated DOUBLE PRECISION,error TEXT);CREATE TABLE IF NOT EXISTS audit(id BIGSERIAL PRIMARY KEY,user_id TEXT,request TEXT,interpretation TEXT,tool TEXT,action TEXT,result TEXT,ts DOUBLE PRECISION);CREATE TABLE IF NOT EXISTS pairing_codes(code TEXT PRIMARY KEY,expires DOUBLE PRECISION);CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY,name TEXT,platform TEXT,public_key TEXT,token_hash TEXT,last_seen DOUBLE PRECISION,status TEXT,data TEXT);CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY,device_id TEXT,action TEXT,payload TEXT,status TEXT,created DOUBLE PRECISION,updated DOUBLE PRECISION,result TEXT);'''
        with self.conn() as c:c.execute(sql);c.commit()
    def exec(self,sql,args=()):
        q=sql.replace('INSERT OR REPLACE','INSERT').replace('VALUES(?,?)','VALUES(%s,%s)')
        q=q.replace('?', '%s')
        with self.conn() as c:c.execute(q,args);c.commit()
    def rows(self,sql,args=()):
        with self.conn() as c:c.execute(sql.replace('?', '%s'),args);return c.fetchall()
    def row(self,sql,args=()):
        r=self.rows(sql,args);return r[0] if r else None
    def message(self,role,content):self.exec('INSERT INTO messages(role,content,ts) VALUES(%s,%s,%s)',(role,content,time.time()))
    def history(self,n=24):return list(reversed(self.rows('SELECT role,content FROM messages ORDER BY id DESC LIMIT %s',(n,))))
    def remember(self,uid,kind,content,weight=.8,source='conversation',provenance=None):self.exec('INSERT INTO memories(user_id,kind,content,weight,source,provenance,ts) VALUES(%s,%s,%s,%s,%s,%s,%s)',(uid,kind,content,weight,source,json.dumps(provenance or {}),time.time()))
    def memories(self,uid,q='',limit=20):
        if q:return self.rows('SELECT kind,content,weight,source,provenance,ts FROM memories WHERE user_id=%s AND content ILIKE %s ORDER BY weight DESC,ts DESC LIMIT %s',(uid,'%'+q+'%',limit))
        return self.rows('SELECT kind,content,weight,source,provenance,ts FROM memories WHERE user_id=%s ORDER BY weight DESC,ts DESC LIMIT %s',(uid,limit))
    def entity(self,eid,kind,name,data):self.exec('INSERT INTO entities(id,kind,name,data,updated) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET kind=EXCLUDED.kind,name=EXCLUDED.name,data=EXCLUDED.data,updated=EXCLUDED.updated',(eid,kind,name,json.dumps(data),time.time()))
    def entities(self):return self.rows('SELECT * FROM entities ORDER BY updated DESC')
    def relation(self,s,p,o,confidence=1.,source='system'):self.exec('INSERT INTO relations(subject,predicate,object,confidence,source,ts) VALUES(%s,%s,%s,%s,%s,%s)',(s,p,o,confidence,source,time.time()))
    def relations(self):return self.rows('SELECT * FROM relations ORDER BY ts DESC')
    def fact(self,statement,source,url='',confidence=.5,metadata=None):
        fid=str(uuid.uuid4());self.exec('INSERT INTO facts(id,statement,source,url,confidence,retrieved,metadata) VALUES(%s,%s,%s,%s,%s,%s,%s)',(fid,statement,source,url,confidence,time.time(),json.dumps(metadata or {})));return fid
    def facts(self,n=100):return self.rows('SELECT * FROM facts ORDER BY retrieved DESC LIMIT %s',(n,))
    def task(self,objective,state='PENDING',priority=0,handler='',data=None,run_at=None,interval_sec=None):
        tid=str(uuid.uuid4());now=time.time();self.exec('INSERT INTO tasks(id,objective,state,priority,handler,data,run_at,interval_sec,retries,created,updated,error) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',(tid,objective,state,priority,handler,json.dumps(data or {}),run_at,interval_sec,0,now,now,''));return tid
    def tasks(self,state=None):
        q='SELECT * FROM tasks';args=()
        if state:q+=' WHERE state=%s';args=(state,)
        q+=' ORDER BY priority DESC,created ASC';return self.rows(q,args)
    def task_update(self,tid,**fields):
        if not fields:return
        fields['updated']=time.time();cols=','.join(f'{k}=%s' for k in fields);self.exec(f'UPDATE tasks SET {cols} WHERE id=%s',(*fields.values(),tid))
    def audit(self,*args):self.exec('INSERT INTO audit(user_id,request,interpretation,tool,action,result,ts) VALUES(%s,%s,%s,%s,%s,%s,%s)',(*args,time.time()))
    def audit_recent(self,n=200):return self.rows('SELECT * FROM audit ORDER BY id DESC LIMIT %s',(n,))
    def create_pair_code(self,ttl=300):
        code=secrets.token_urlsafe(8).replace('-','').replace('_','')[:8].upper();self.exec('INSERT INTO pairing_codes(code,expires) VALUES(%s,%s) ON CONFLICT(code) DO UPDATE SET expires=EXCLUDED.expires',(code,time.time()+ttl));return code
    def consume_pair_code(self,code):
        r=self.row('SELECT expires FROM pairing_codes WHERE code=%s',(code.upper(),));ok=bool(r and r['expires']>time.time())
        if ok:self.exec('DELETE FROM pairing_codes WHERE code=%s',(code.upper(),))
        return ok
    def pair_device(self,id,name,platform,public_key,token):self.exec('INSERT INTO devices(id,name,platform,public_key,token_hash,last_seen,status,data) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET name=EXCLUDED.name,platform=EXCLUDED.platform,public_key=EXCLUDED.public_key,token_hash=EXCLUDED.token_hash,last_seen=EXCLUDED.last_seen,status=EXCLUDED.status',(id,name,platform,public_key,hashlib.sha256(token.encode()).hexdigest(),time.time(),'ONLINE','{}'))
    def device_token_valid(self,id,token):
        r=self.row('SELECT token_hash FROM devices WHERE id=%s',(id,));return bool(r and secrets.compare_digest(r['token_hash'],hashlib.sha256(token.encode()).hexdigest()))
    def heartbeat(self,id,status='ONLINE'):self.exec('UPDATE devices SET last_seen=%s,status=%s WHERE id=%s',(time.time(),status,id))
    def devices(self):return self.rows('SELECT id,name,platform,last_seen,status,data FROM devices ORDER BY name')
    def queue_command(self,device_id,action,payload):
        cid=str(uuid.uuid4());now=time.time();self.exec('INSERT INTO commands(id,device_id,action,payload,status,created,updated,result) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',(cid,device_id,action,json.dumps(payload or {}),'PENDING',now,now,''));return cid
    def pull_commands(self,device_id,limit=20):
        rows=self.rows('SELECT * FROM commands WHERE device_id=%s AND status=\'PENDING\' ORDER BY created LIMIT %s',(device_id,limit))
        for r in rows:self.exec('UPDATE commands SET status=%s,updated=%s WHERE id=%s',('DELIVERED',time.time(),r['id']));r['payload']=json.loads(r['payload'])
        return rows
    def command_result(self,cid,status,result):self.exec('UPDATE commands SET status=%s,result=%s,updated=%s WHERE id=%s',(status,json.dumps(result),time.time(),cid))
