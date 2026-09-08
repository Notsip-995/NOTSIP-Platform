from __future__ import annotations
import hashlib,json,os,secrets,time,uuid
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
            c.execute(sql);c.execute('CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY,kind TEXT,name TEXT,data TEXT,updated DOUBLE PRECISION)');c.execute('CREATE TABLE IF NOT EXISTS relations(id BIGSERIAL PRIMARY KEY,subject TEXT,predicate TEXT,object TEXT,confidence DOUBLE PRECISION,source TEXT,ts DOUBLE PRECISION)');c.execute('CREATE TABLE IF NOT EXISTS facts(id TEXT PRIMARY KEY,statement TEXT,source TEXT,url TEXT,confidence DOUBLE PRECISION,retrieved DOUBLE PRECISION,metadata TEXT)');c.execute('CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,objective TEXT,state TEXT,priority INTEGER,handler TEXT,data TEXT,run_at DOUBLE PRECISION,interval_sec DOUBLE PRECISION,retries INTEGER,created DOUBLE PRECISION,updated DOUBLE PRECISION,error TEXT,idempotency_key TEXT DEFAULT \'\')');c.execute('CREATE TABLE IF NOT EXISTS audit(id BIGSERIAL PRIMARY KEY,user_id TEXT,request TEXT,interpretation TEXT,tool TEXT,action TEXT,result TEXT,ts DOUBLE PRECISION)');c.execute('CREATE TABLE IF NOT EXISTS pairing_codes(code TEXT PRIMARY KEY,expires DOUBLE PRECISION)');c.execute('CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY,name TEXT,platform TEXT,public_key TEXT,token_hash TEXT,last_seen DOUBLE PRECISION,status TEXT,data TEXT)');c.execute('CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY,device_id TEXT,action TEXT,payload TEXT,status TEXT,created DOUBLE PRECISION,updated DOUBLE PRECISION,result TEXT)');cols={r['column_name'] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_name='tasks'").fetchall()};
            if 'idempotency_key' not in cols:c.execute("ALTER TABLE tasks ADD COLUMN idempotency_key TEXT DEFAULT ''")
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_idempotency_key ON tasks(idempotency_key) WHERE idempotency_key <> ''");c.commit()
    def exec(self,sql,args=()):
        q=sql.replace('INSERT OR REPLACE','INSERT').replace('VALUES(?,?)','VALUES(%s,%s)').replace('?','%s')
        with self.conn() as c:c.execute(q,args);c.commit()
    def rows(self,sql,args=()):
        with self.conn() as c:c.execute(sql.replace('?','%s'),args);return c.fetchall()
    def row(self,sql,args=()):r=self.rows(sql,args);return r[0] if r else None
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
    def task(self,objective,state='PENDING',priority=0,handler='',data=None,run_at=None,interval_sec=None,idempotency_key=''):
        tid=str(uuid.uuid4());now=time.time();payload=json.dumps(data or {})
        with self.conn() as c:
            if idempotency_key:
                row=c.execute('INSERT INTO tasks(id,objective,state,priority,handler,data,run_at,interval_sec,retries,created,updated,error,idempotency_key) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id',(tid,objective,state,priority,handler,payload,run_at,interval_sec,0,now,now,'',idempotency_key)).fetchone()
                if row:c.commit();return row['id']
                existing=c.execute('SELECT id FROM tasks WHERE idempotency_key=%s',(idempotency_key,)).fetchone();c.commit()
                if existing:return existing['id']
                raise RuntimeError('task idempotency conflict could not be resolved')
            row=c.execute('INSERT INTO tasks(id,objective,state,priority,handler,data,run_at,interval_sec,retries,created,updated,error,idempotency_key) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id',(tid,objective,state,priority,handler,payload,run_at,interval_sec,0,now,now,'','')).fetchone();c.commit();return row['id']
    def tasks(self,state=None):
        q='SELECT * FROM tasks';args=()
        if state:q+=' WHERE state=%s';args=(state,)
        q+=' ORDER BY priority DESC,created ASC';return self.rows(q,args)
    def claim_task(self,tid,data):
        with self.conn() as c:row=c.execute("UPDATE tasks SET state='RUNNING',data=%s,error='',updated=%s WHERE id=%s AND state='PENDING' RETURNING id",(data,time.time(),tid)).fetchone();c.commit();return bool(row)
    def task_update(self,tid,**fields):
        if not fields:return
        fields['updated']=time.time();cols=','.join(f'{k}=%s' for k in fields);self.exec(f'UPDATE tasks SET {cols} WHERE id=%s',(*fields.values(),tid))
    def restore_runtime_state(self,state):
        tasks=state.get('tasks') or [];world=state.get('world') or {};devices=state.get('devices') or [];commands=state.get('commands') or []
        with self.conn() as c:
            existing_tokens={r['id']:r['token_hash'] for r in c.execute('SELECT id,token_hash FROM devices').fetchall()}
            for table in ('commands','tasks','devices','entities','relations','facts'):c.execute(f'DELETE FROM {table}')
            for t in tasks:c.execute('INSERT INTO tasks(id,objective,state,priority,handler,data,run_at,interval_sec,retries,created,updated,error,idempotency_key) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',(t.get('id') or str(uuid.uuid4()),t.get('objective',''),t.get('state','PENDING'),int(t.get('priority',0)),t.get('handler','agent'),t.get('data','{}') if isinstance(t.get('data','{}'),str) else json.dumps(t.get('data') or {}),t.get('run_at'),t.get('interval_sec'),int(t.get('retries',0)),float(t.get('created',time.time())),float(t.get('updated',time.time())),t.get('error',''),t.get('idempotency_key','') or ''))
            for d in devices:
                device_id=d.get('id','');token_hash=d.get('token_hash') or existing_tokens.get(device_id,'');status=d.get('status','') if token_hash else 'REPAIR_REQUIRED';data=d.get('data','{}') if isinstance(d.get('data','{}'),str) else json.dumps(d.get('data') or {});c.execute('INSERT INTO devices(id,name,platform,public_key,token_hash,last_seen,status,data) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',(device_id,d.get('name',''),d.get('platform',''),d.get('public_key',''),token_hash,d.get('last_seen'),status,data))
            for cmd in commands:c.execute('INSERT INTO commands(id,device_id,action,payload,status,created,updated,result) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',(cmd.get('id') or str(uuid.uuid4()),cmd.get('device_id',''),cmd.get('action',''),cmd.get('payload','{}') if isinstance(cmd.get('payload','{}'),str) else json.dumps(cmd.get('payload') or {}),cmd.get('status','PENDING'),float(cmd.get('created',time.time())),float(cmd.get('updated',time.time())),cmd.get('result','{}') if isinstance(cmd.get('result','{}'),str) else json.dumps(cmd.get('result') or {})))
            for e in world.get('entities') or []:c.execute('INSERT INTO entities(id,kind,name,data,updated) VALUES(%s,%s,%s,%s,%s)',(e.get('id',''),e.get('kind',''),e.get('name',''),e.get('data','{}') if isinstance(e.get('data','{}'),str) else json.dumps(e.get('data') or {}),float(e.get('updated',time.time()))))
            for r in world.get('relations') or []:c.execute('INSERT INTO relations(id,subject,predicate,object,confidence,source,ts) VALUES(%s,%s,%s,%s,%s,%s,%s)',(r.get('id'),r.get('subject',''),r.get('predicate',''),r.get('object',''),float(r.get('confidence',1)),r.get('source','recovery'),float(r.get('ts',time.time()))))
            for f in world.get('facts') or []:c.execute('INSERT INTO facts(id,statement,source,url,confidence,retrieved,metadata) VALUES(%s,%s,%s,%s,%s,%s,%s)',(f.get('id') or str(uuid.uuid4()),f.get('statement',''),f.get('source','recovery'),f.get('url',''),float(f.get('confidence',.5)),float(f.get('retrieved',time.time())),f.get('metadata','{}') if isinstance(f.get('metadata','{}'),str) else json.dumps(f.get('metadata') or {})))
            c.commit()
        return {'status':'RESTORED','tasks':len(tasks),'devices':len(devices),'commands':len(commands),'entities':len(world.get('entities') or []),'relations':len(world.get('relations') or []),'facts':len(world.get('facts') or [])}
    def audit(self,*args):self.exec('INSERT INTO audit(user_id,request,interpretation,tool,action,result,ts) VALUES(%s,%s,%s,%s,%s,%s,%s)',(*args,time.time()))
    def audit_recent(self,n=200):return self.rows('SELECT * FROM audit ORDER BY id DESC LIMIT %s',(n,))
    def create_pair_code(self,ttl=300):
        code=secrets.token_urlsafe(8).replace('-','').replace('_','')[:8].upper();self.exec('INSERT INTO pairing_codes(code,expires) VALUES(%s,%s) ON CONFLICT(code) DO UPDATE SET expires=EXCLUDED.expires',(code,time.time()+ttl));return code
    def consume_pair_code(self,code):
        with self.conn() as c:row=c.execute("DELETE FROM pairing_codes WHERE code=%s AND expires>%s RETURNING code",(code.upper(),time.time())).fetchone();c.commit();return bool(row)
    def _owner(self,owner=None):return str(owner or current_actor()).strip() or 'primary-user'
    def pair_device(self,id,name,platform,public_key,token,owner=None):
        owner=self._owner(owner);existing=self.row('SELECT data FROM devices WHERE id=%s',(id,))
        if existing:
            try:existing_owner=json.loads(existing['data'] or '{}').get('owner')
            except (TypeError,ValueError):raise PermissionError('existing device metadata is corrupt; ownership cannot be reassigned')
            if existing_owner not in (None,owner):raise PermissionError('device is already owned by another actor')
        data=json.loads(existing['data'] or '{}') if existing else {};data['owner']=owner
        self.exec('INSERT INTO devices(id,name,platform,public_key,token_hash,last_seen,status,data) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET name=EXCLUDED.name,platform=EXCLUDED.platform,public_key=EXCLUDED.public_key,token_hash=EXCLUDED.token_hash,last_seen=EXCLUDED.last_seen,status=EXCLUDED.status,data=EXCLUDED.data',(id,name,platform,public_key,hashlib.sha256(token.encode()).hexdigest(),time.time(),'ONLINE',json.dumps(data)))
    def device_owner(self,id):
        r=self.row('SELECT data FROM devices WHERE id=%s',(id,));
        if not r:return None
        try:
            data=json.loads(r.get('data') or '{}');owner=data.get('owner','primary-user');return owner if isinstance(owner,str) and owner.strip() else None
        except (TypeError,ValueError):return None
    def device_owned_by(self,id,owner=None):return self.device_owner(id)==self._owner(owner)
    def device_token_valid(self,id,token):r=self.row('SELECT token_hash FROM devices WHERE id=%s',(id,));return bool(r and secrets.compare_digest(r['token_hash'],hashlib.sha256(token.encode()).hexdigest()))
    def heartbeat(self,id,status='ONLINE'):self.exec('UPDATE devices SET last_seen=%s,status=%s WHERE id=%s',(time.time(),status,id))
    def devices(self,owner=None):
        owner=self._owner(owner);out=[]
        for row in self.rows('SELECT id,name,platform,last_seen,status,data FROM devices ORDER BY name'):
            try:row_owner=json.loads(row.get('data') or '{}').get('owner','primary-user')
            except (TypeError,ValueError):row_owner=None
            if row_owner==owner:out.append(row)
        return out
    def queue_command(self,device_id,action,payload):
        if not self.device_owned_by(device_id):raise PermissionError('device is not owned by current actor')
        cid=str(uuid.uuid4());now=time.time();self.exec('INSERT INTO commands(id,device_id,action,payload,status,created,updated,result) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',(cid,device_id,action,json.dumps(payload or {}),'PENDING',now,now,''));return cid
    def pull_commands(self,device_id,limit=20):
        with self.conn() as c:
            rows=c.execute("WITH claimed AS (SELECT id FROM commands WHERE device_id=%s AND status='PENDING' ORDER BY created LIMIT %s) UPDATE commands SET status='DELIVERED',updated=%s WHERE id IN (SELECT id FROM claimed) RETURNING *",(device_id,limit,time.time())).fetchall();c.commit();return [{**dict(r),'payload':json.loads(r['payload'])} for r in rows]
    def reconcile_commands(self,lease_seconds=None):
        lease=max(30,int(lease_seconds or os.getenv('NOTSIP_COMMAND_LEASE_SECONDS','300')));cutoff=time.time()-lease
        with self.conn() as c:
            rows=c.execute("SELECT c.id,c.device_id,c.action,d.status AS device_status,d.last_seen FROM commands c LEFT JOIN devices d ON d.id=c.device_id WHERE c.status='DELIVERED' AND c.updated<? AND (d.id IS NULL OR d.status='STALE' OR d.status='REVOKED' OR d.last_seen<?)",(cutoff,cutoff)).fetchall()
            if rows:c.executemany("UPDATE commands SET status='UNKNOWN',updated=%s,result=%s WHERE id=%s AND status='DELIVERED'",[(time.time(),json.dumps({'verified':False,'reason':'device was removed, revoked, or did not return a command result before lease expiry'}),r['id']) for r in rows])
            c.commit();return [dict(r) for r in rows]
    def command_result(self,cid,status,result,device_id=None):
        if device_id is None:q='UPDATE commands SET status=%s,result=%s,updated=%s WHERE id=%s';args=(status,json.dumps(result),time.time(),cid)
        else:q='UPDATE commands SET status=%s,result=%s,updated=%s WHERE id=%s AND device_id=%s';args=(status,json.dumps(result),time.time(),cid,device_id)
        with self.conn() as c:cur=c.execute(q,args);c.commit();return cur.rowcount==1
