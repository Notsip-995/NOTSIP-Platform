from __future__ import annotations
import hashlib,json,os,secrets,time,uuid
from pathlib import Path
import psycopg
from .actor_context import current_actor

class PostgreSQLStore:
    def __init__(self,root,url):self.root=Path(root);self.url=url;self.lock=None;self.init()
    def conn(self):return psycopg.connect(self.url,row_factory=psycopg.rows.dict_row)
    def init(self):
        with self.conn() as c:
            c.execute('''CREATE TABLE IF NOT EXISTS messages(id BIGSERIAL PRIMARY KEY,role TEXT,content TEXT,ts DOUBLE PRECISION);CREATE TABLE IF NOT EXISTS memories(id BIGSERIAL PRIMARY KEY,user_id TEXT,kind TEXT,content TEXT,weight DOUBLE PRECISION,source TEXT,provenance JSONB,ts DOUBLE PRECISION);CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY,kind TEXT,name TEXT,data JSONB,updated DOUBLE PRECISION);CREATE TABLE IF NOT EXISTS relations(id BIGSERIAL PRIMARY KEY,subject TEXT,predicate TEXT,object TEXT,confidence DOUBLE PRECISION,source TEXT,ts DOUBLE PRECISION);CREATE TABLE IF NOT EXISTS facts(id TEXT PRIMARY KEY,statement TEXT,source TEXT,url TEXT,confidence DOUBLE PRECISION,retrieved DOUBLE PRECISION,metadata JSONB);CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,objective TEXT,state TEXT,priority INTEGER,handler TEXT,data JSONB,run_at DOUBLE PRECISION,interval_sec DOUBLE PRECISION,retries INTEGER,created DOUBLE PRECISION,updated DOUBLE PRECISION,error TEXT,idempotency_key TEXT DEFAULT '');CREATE TABLE IF NOT EXISTS audit(id BIGSERIAL PRIMARY KEY,user_id TEXT,request TEXT,interpretation TEXT,tool TEXT,action TEXT,result TEXT,ts DOUBLE PRECISION);CREATE TABLE IF NOT EXISTS pairing_codes(code TEXT PRIMARY KEY,expires DOUBLE PRECISION);CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY,name TEXT,platform TEXT,public_key TEXT,token_hash TEXT,last_seen DOUBLE PRECISION,status TEXT,data JSONB);CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY,device_id TEXT,action TEXT,payload JSONB,status TEXT,created DOUBLE PRECISION,updated DOUBLE PRECISION,result JSONB);CREATE TABLE IF NOT EXISTS node_nonces(node_id TEXT NOT NULL,nonce TEXT NOT NULL,expires DOUBLE PRECISION NOT NULL,PRIMARY KEY(node_id,nonce));CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_idempotency_key ON tasks(idempotency_key) WHERE idempotency_key <> '';''')
            c.commit()
    def exec(self,sql,args=()):
        with self.conn() as c:c.execute(sql,args);c.commit()
    def rows(self,sql,args=()):
        with self.conn() as c:return c.execute(sql,args).fetchall()
    def row(self,sql,args=()):r=self.rows(sql,args);return r[0] if r else None
    def remember(self,uid,kind,content,weight=.8,source='conversation',provenance=None):self.exec('INSERT INTO memories(user_id,kind,content,weight,source,provenance,ts) VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s)',(uid,kind,content,weight,source,json.dumps(provenance or {}),time.time()))
    def memories(self,uid,q='',limit=20):return [dict(r) for r in self.rows('SELECT kind,content,weight,source,provenance,ts FROM memories WHERE user_id=%s ORDER BY weight DESC,ts DESC LIMIT %s',(uid,limit))]
    def entity(self,eid,kind,name,data):self.exec('INSERT INTO entities(id,kind,name,data,updated) VALUES(%s,%s,%s,%s::jsonb,%s) ON CONFLICT(id) DO UPDATE SET kind=EXCLUDED.kind,name=EXCLUDED.name,data=EXCLUDED.data,updated=EXCLUDED.updated',(eid,kind,name,json.dumps(data),time.time()))
    def entities(self):return [dict(r) for r in self.rows('SELECT * FROM entities ORDER BY updated DESC')]
    def relation(self,s,p,o,confidence=1.,source='system'):self.exec('INSERT INTO relations(subject,predicate,object,confidence,source,ts) VALUES(%s,%s,%s,%s,%s,%s)',(s,p,o,confidence,source,time.time()))
    def relations(self):return [dict(r) for r in self.rows('SELECT * FROM relations ORDER BY ts DESC')]
    def fact(self,statement,source,url='',confidence=.5,metadata=None):fid=str(uuid.uuid4());self.exec('INSERT INTO facts(id,statement,source,url,confidence,retrieved,metadata) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb)',(fid,statement,source,url,confidence,time.time(),json.dumps(metadata or {})));return fid
    def facts(self,n=100):return [dict(r) for r in self.rows('SELECT * FROM facts ORDER BY retrieved DESC LIMIT %s',(n,))]
    def task(self,objective,state='PENDING',priority=0,handler='',data=None,run_at=None,interval_sec=None,idempotency_key=''):
        if idempotency_key:
            existing=self.row('SELECT id FROM tasks WHERE idempotency_key=%s',(idempotency_key,))
            if existing:return existing['id']
        tid=str(uuid.uuid4());now=time.time();self.exec('INSERT INTO tasks(id,objective,state,priority,handler,data,run_at,interval_sec,retries,created,updated,error,idempotency_key) VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s,0,%s,%s,%s,%s)',(tid,objective,state,priority,handler,json.dumps(data or {}),run_at,interval_sec,now,now,'',idempotency_key or ''));return tid
    def tasks(self,state=None):return [dict(r) for r in self.rows('SELECT * FROM tasks WHERE state=%s ORDER BY priority DESC,created ASC',(state,))] if state else [dict(r) for r in self.rows('SELECT * FROM tasks ORDER BY priority DESC,created ASC')]
    def claim_task(self,tid,data):
        with self.conn() as c:cur=c.execute("UPDATE tasks SET state='RUNNING',data=%s::jsonb,error='',updated=%s WHERE id=%s AND state='PENDING'",(data,time.time(),tid));c.commit();return cur.rowcount==1
    def task_update(self,tid,**fields):
        if fields:self.exec('UPDATE tasks SET '+','.join(f'{k}=%s' for k in fields)+' WHERE id=%s',(*fields.values(),tid))
    def restore_runtime_state(self,state):
        world=state.get('world') or {}
        with self.conn() as c:
            c.execute('DELETE FROM commands');c.execute('DELETE FROM tasks');c.execute('DELETE FROM devices');c.execute('DELETE FROM entities');c.execute('DELETE FROM relations');c.execute('DELETE FROM facts')
            for t in state.get('tasks') or []:c.execute('INSERT INTO tasks(id,objective,state,priority,handler,data,run_at,interval_sec,retries,created,updated,error,idempotency_key) VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s)',(t.get('id') or str(uuid.uuid4()),t.get('objective',''),t.get('state','PENDING'),int(t.get('priority',0)),t.get('handler','agent'),t.get('data','{}') if isinstance(t.get('data','{}'),str) else json.dumps(t.get('data') or {}),t.get('run_at'),t.get('interval_sec'),int(t.get('retries',0)),float(t.get('created',time.time())),float(t.get('updated',time.time())),t.get('error',''),t.get('idempotency_key','') or ''))
            for d in state.get('devices') or []:c.execute('INSERT INTO devices(id,name,platform,public_key,token_hash,last_seen,status,data) VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb)',(d.get('id',''),d.get('name',''),d.get('platform',''),d.get('public_key',''),d.get('token_hash',''),d.get('last_seen'),d.get('status','REPAIR_REQUIRED'),d.get('data','{}') if isinstance(d.get('data','{}'),str) else json.dumps(d.get('data') or {})))
            for cmd in state.get('commands') or []:c.execute('INSERT INTO commands(id,device_id,action,payload,status,created,updated,result) VALUES(%s,%s,%s,%s::jsonb,%s,%s,%s,%s::jsonb)',(cmd.get('id') or str(uuid.uuid4()),cmd.get('device_id',''),cmd.get('action',''),cmd.get('payload','{}') if isinstance(cmd.get('payload','{}'),str) else json.dumps(cmd.get('payload') or {}),cmd.get('status','PENDING'),float(cmd.get('created',time.time())),float(cmd.get('updated',time.time())),cmd.get('result','{}') if isinstance(cmd.get('result','{}'),str) else json.dumps(cmd.get('result') or {})))
            for e in world.get('entities') or []:c.execute('INSERT INTO entities(id,kind,name,data,updated) VALUES(%s,%s,%s,%s::jsonb,%s)',(e.get('id',''),e.get('kind',''),e.get('name',''),e.get('data','{}') if isinstance(e.get('data','{}'),str) else json.dumps(e.get('data') or {}),float(e.get('updated',time.time()))))
            for r in world.get('relations') or []:c.execute('INSERT INTO relations(subject,predicate,object,confidence,source,ts) VALUES(%s,%s,%s,%s,%s,%s)',(r.get('subject',''),r.get('predicate',''),r.get('object',''),float(r.get('confidence',1)),r.get('source','recovery'),float(r.get('ts',time.time()))))
            for f in world.get('facts') or []:c.execute('INSERT INTO facts(id,statement,source,url,confidence,retrieved,metadata) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb)',(f.get('id') or str(uuid.uuid4()),f.get('statement',''),f.get('source','recovery'),f.get('url',''),float(f.get('confidence',.5)),float(f.get('retrieved',time.time())),f.get('metadata','{}') if isinstance(f.get('metadata','{}'),str) else json.dumps(f.get('metadata') or {})))
            c.commit()
        return {'status':'RESTORED','tasks':len(state.get('tasks') or []),'devices':len(state.get('devices') or []),'commands':len(state.get('commands') or []),'entities':len(world.get('entities') or []),'relations':len(world.get('relations') or []),'facts':len(world.get('facts') or [])}
    def audit(self,*args):self.exec('INSERT INTO audit(user_id,request,interpretation,tool,action,result,ts) VALUES(%s,%s,%s,%s,%s,%s,%s)',(*args,time.time()))
    def audit_recent(self,n=200):return [dict(r) for r in self.rows('SELECT * FROM audit ORDER BY id DESC LIMIT %s',(n,))]
    def create_pair_code(self,ttl=300):code=secrets.token_urlsafe(8).replace('-','').replace('_','')[:8].upper();self.exec('INSERT INTO pairing_codes(code,expires) VALUES(%s,%s) ON CONFLICT(code) DO UPDATE SET expires=EXCLUDED.expires',(code,time.time()+ttl));return code
    def consume_pair_code(self,code):
        with self.conn() as c:r=c.execute('DELETE FROM pairing_codes WHERE code=%s AND expires>%s RETURNING code',(code.upper(),time.time())).fetchone();c.commit();return bool(r)
    def device_owner(self,id):r=self.row('SELECT data FROM devices WHERE id=%s',(id,));return (r.get('data') or {}).get('owner') if r else None
    def device_owned_by(self,id,owner=None):return self.device_owner(id)==str(owner or current_actor()).strip()
    def pair_device(self,id,name,platform,public_key,token,owner=None):
        owner=str(owner or current_actor()).strip() or 'primary-user';row=self.row('SELECT data FROM devices WHERE id=%s',(id,))
        if row:
            existing=(row.get('data') or {}).get('owner')
            if existing not in (None,owner):raise PermissionError('device is already owned by another actor')
        data=(row.get('data') or {}) if row else {};data['owner']=owner;self.exec('INSERT INTO devices(id,name,platform,public_key,token_hash,last_seen,status,data) VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT(id) DO UPDATE SET name=EXCLUDED.name,platform=EXCLUDED.platform,public_key=EXCLUDED.public_key,token_hash=EXCLUDED.token_hash,last_seen=EXCLUDED.last_seen,status=EXCLUDED.status,data=EXCLUDED.data',(id,name,platform,public_key,hashlib.sha256(token.encode()).hexdigest(),time.time(),'ONLINE',json.dumps(data)))
    def devices(self,owner=None):
        owner=str(owner or current_actor()).strip() or 'primary-user';return [dict(r) for r in self.rows("SELECT id,name,platform,last_seen,status,data FROM devices WHERE data->>'owner'=%s ORDER BY name",(owner,))]
    def device_token_valid(self,id,token):r=self.row('SELECT token_hash FROM devices WHERE id=%s',(id,));return bool(r and secrets.compare_digest(r['token_hash'],hashlib.sha256(token.encode()).hexdigest()))
    def queue_command(self,device_id,action,payload):
        if not self.device_owned_by(device_id):raise PermissionError('device is not owned by current actor')
        cid=str(uuid.uuid4());now=time.time();self.exec('INSERT INTO commands(id,device_id,action,payload,status,created,updated,result) VALUES(%s,%s,%s,%s::jsonb,%s,%s,%s,%s::jsonb)',(cid,device_id,action,json.dumps(payload or {}),'PENDING',now,now,'{}'));return cid
    def pull_commands(self,device_id,limit=20):
        with self.conn() as c:
            rows=c.execute("SELECT * FROM commands WHERE device_id=%s AND status='PENDING' ORDER BY created FOR UPDATE SKIP LOCKED LIMIT %s",(device_id,limit)).fetchall();ids=[r['id'] for r in rows]
            if ids:c.execute("UPDATE commands SET status='DELIVERED',updated=%s WHERE id=ANY(%s) AND status='PENDING'",(time.time(),ids))
            c.commit();return [dict(r) for r in rows]
    def reconcile_commands(self,lease_seconds=None):
        lease=max(30,int(lease_seconds or os.getenv('NOTSIP_COMMAND_LEASE_SECONDS','300')));cutoff=time.time()-lease
        with self.conn() as c:
            rows=c.execute("SELECT c.id,c.device_id,c.action,d.status AS device_status,d.last_seen FROM commands c LEFT JOIN devices d ON d.id=c.device_id WHERE c.status='DELIVERED' AND c.updated<%s AND (d.id IS NULL OR d.status='STALE' OR d.status='REVOKED' OR d.last_seen<%s)",(cutoff,cutoff)).fetchall()
            if rows:c.executemany("UPDATE commands SET status='UNKNOWN',updated=%s,result=%s::jsonb WHERE id=%s AND status='DELIVERED'",[(time.time(),json.dumps({'verified':False,'reason':'device did not return a command result before lease expiry'}),r['id']) for r in rows])
            c.commit();return [dict(r) for r in rows]
    def command_result(self,cid,status,result,device_id=None):
        if device_id is None:return False
        with self.conn() as c:cur=c.execute("UPDATE commands SET status=%s,result=%s::jsonb,updated=%s WHERE id=%s AND device_id=%s AND status='DELIVERED'",(status,json.dumps(result),time.time(),cid,device_id));c.commit();return cur.rowcount==1
