from __future__ import annotations
import hashlib,hmac,json,os,secrets,time,uuid
from pathlib import Path
class NodeRegistry:
    def __init__(self,store,secret='',lease_seconds=None):
        self.store=store;self.secret=secret or '';self.lease_seconds=int(lease_seconds or os.getenv('NOTSIP_NODE_LEASE_SECONDS','90'))
        self.store.exec('CREATE TABLE IF NOT EXISTS node_nonces(node_id TEXT NOT NULL,nonce TEXT NOT NULL,expires REAL NOT NULL,PRIMARY KEY(node_id,nonce))')
    def _require_shared_secret(self):
        if not self.secret:raise PermissionError('federation shared secret is not configured')
    def sign(self,node_id,nonce):self._require_shared_secret();return hmac.new(self.secret.encode(),f'{node_id}:{nonce}'.encode(),hashlib.sha256).hexdigest()
    def verify(self,node_id,nonce,signature):self._require_shared_secret();return bool(signature) and bool(nonce) and hmac.compare_digest(self.sign(node_id,nonce),signature)
    def _consume_nonce(self,node_id,nonce,ttl=600):
        now=time.time();self.store.exec('DELETE FROM node_nonces WHERE expires<=?',(now,))
        try:self.store.exec('INSERT INTO node_nonces(node_id,nonce,expires) VALUES(?,?,?)',(node_id,nonce,now+ttl));return True
        except Exception:return False
    def register(self,node_id,name,platform,capabilities=None,public_key='',nonce='',signature=''):
        if not self.verify(node_id,nonce,signature):raise PermissionError('invalid federation signature')
        if not self._consume_nonce(node_id,nonce):raise PermissionError('replayed federation nonce')
        token=secrets.token_urlsafe(32);now=time.time();self.store.pair_device(node_id,name,platform,public_key,token);self.store.exec('UPDATE devices SET data=? WHERE id=?',(json.dumps({'capabilities':capabilities or [],'lease_expires':now+self.lease_seconds,'registered_at':now,'node_epoch':1}),node_id));return {'node_id':node_id,'token':token,'lease_seconds':self.lease_seconds}
    def heartbeat(self,node_id,token,capabilities=None,health=None,nonce='',signature=''):
        if not self.store.device_token_valid(node_id,token):raise PermissionError('invalid node token')
        if not self.verify(node_id,nonce,signature):raise PermissionError('invalid federation signature')
        if not self._consume_nonce(node_id,nonce):raise PermissionError('replayed federation nonce')
        data=self.store.row('SELECT data,status FROM devices WHERE id=?',(node_id,));cur=json.loads(data['data'] or '{}') if data else {};cur.update({'capabilities':capabilities or cur.get('capabilities',[]),'health':health or {},'lease_expires':time.time()+self.lease_seconds,'last_heartbeat':time.time()});self.store.exec('UPDATE devices SET last_seen=?,status=?,data=? WHERE id=?',(time.time(),'ONLINE',json.dumps(cur),node_id));return cur
    def rotate(self,node_id):
        if not self.store.row('SELECT id FROM devices WHERE id=?',(node_id,)):raise KeyError(node_id)
        token=secrets.token_urlsafe(32);self.store.exec('UPDATE devices SET token_hash=?,status=? WHERE id=?',(hashlib.sha256(token.encode()).hexdigest(),'ONLINE',node_id));return {'node_id':node_id,'token':token,'rotated_at':time.time()}
    def revoke(self,node_id):self.store.exec("UPDATE devices SET token_hash='',status='REVOKED' WHERE id=?",(node_id,));return {'node_id':node_id,'status':'REVOKED'}
    def reconcile(self):
        now=time.time();out=[]
        for r in self.store.rows('SELECT id,data,status FROM devices'):
            d=json.loads(r['data'] or '{}');exp=d.get('lease_expires');
            if exp is None:status=r['status']
            else:status=r['status'] if r['status']=='REVOKED' else ('ONLINE' if float(exp)>now else 'STALE')
            if status!=r['status']:self.store.exec('UPDATE devices SET status=? WHERE id=?',(status,r['id']))
            out.append({'id':r['id'],'status':status,'lease_expires':exp,'capabilities':d.get('capabilities',[])})
        return out
    def recovery_plan(self):
        nodes=self.reconcile();return {'generated_at':time.time(),'nodes':nodes,'actions':[{'node':n['id'],'action':'redispatch_or_recover'} for n in nodes if n['status']=='STALE']}
class RecoveryManager:
    def __init__(self,root:Path):self.root=Path(root);self.dir=self.root/'recovery';self.dir.mkdir(parents=True,exist_ok=True)
    def checkpoint(self,state):
        name=f'checkpoint-{int(time.time())}-{uuid.uuid4().hex[:8]}.json';p=self.dir/name;payload=json.dumps(state,indent=2,sort_keys=True);digest=hashlib.sha256(payload.encode()).hexdigest();tmp=p.with_suffix('.tmp');tmp.write_text(payload,encoding='utf-8');tmp.replace(p);p.with_suffix('.sha256').write_text(digest+'  '+name+'\n',encoding='utf-8');return str(p.relative_to(self.root))
    def _files(self):return sorted(self.dir.glob('checkpoint-*.json'))
    def latest_path(self):
        files=self._files();return files[-1] if files else None
    def _load_verified(self,p):
        raw=p.read_text(encoding='utf-8');side=p.with_suffix('.sha256')
        if not side.exists():raise RuntimeError('recovery checkpoint integrity manifest is missing')
        expected=side.read_text(encoding='utf-8').split()[0].strip().lower();actual=hashlib.sha256(raw.encode()).hexdigest().lower()
        if expected!=actual:raise RuntimeError('recovery checkpoint integrity verification failed')
        return json.loads(raw)
    def latest(self):
        p=self.latest_path();return self._load_verified(p) if p else None
    def verify_latest(self):
        p=self.latest_path()
        if not p:return {'valid':False,'reason':'no recovery checkpoint available'}
        try:x=self._load_verified(p)
        except Exception as exc:return {'valid':False,'reason':str(exc),'path':str(p.relative_to(self.root))}
        return {'valid':True,'path':str(p.relative_to(self.root)),'has_tasks':'tasks' in x,'has_devices':'devices' in x,'has_commands':'commands' in x,'has_world':'world' in x}
    def restore_state(self):
        x=self.latest();
        if not x:raise RuntimeError('no recovery checkpoint available')
        verification=self.verify_latest()
        if not verification.get('valid'):raise RuntimeError(verification.get('reason','recovery checkpoint failed verification'))
        return {'status':'RECOVERABLE','state':x,'verification':verification}
