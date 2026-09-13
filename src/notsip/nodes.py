from __future__ import annotations
import hashlib,hmac,json,os,secrets,time,uuid
from pathlib import Path
from .actor_context import current_actor
class NodeRegistry:
    def __init__(self,store,secret='',lease_seconds=None):
        self.store=store;self.secret=secret or '';self.lease_seconds=int(lease_seconds or os.getenv('NOTSIP_NODE_LEASE_SECONDS','90'));self.world=None
        self.store.exec('CREATE TABLE IF NOT EXISTS node_nonces(node_id TEXT NOT NULL,nonce TEXT NOT NULL,expires REAL NOT NULL,PRIMARY KEY(node_id,nonce))')
    def _require_shared_secret(self):
        if not self.secret:raise PermissionError('federation shared secret is not configured')
    def _owner(self,owner=None):return str(owner or current_actor()).strip() or 'primary-user'
    def _require_owner(self,node_id,owner=None):
        actor=self._owner(owner)
        if not self.store.device_owned_by(node_id,actor):raise PermissionError('federation node is not owned by current actor')
        return actor
    def sign(self,node_id,nonce):self._require_shared_secret();return hmac.new(self.secret.encode(),f'{node_id}:{nonce}'.encode(),hashlib.sha256).hexdigest()
    def verify(self,node_id,nonce,signature):self._require_shared_secret();return bool(signature) and bool(nonce) and hmac.compare_digest(self.sign(node_id,nonce),signature)
    def _consume_nonce(self,node_id,nonce,ttl=600):
        now=time.time();self.store.exec('DELETE FROM node_nonces WHERE expires<=?',(now,))
        try:self.store.exec('INSERT INTO node_nonces(node_id,nonce,expires) VALUES(?,?,?)',(node_id,nonce,now+ttl));return True
        except Exception as exc:
            existing=self.store.row('SELECT nonce FROM node_nonces WHERE node_id=? AND nonce=?',(node_id,nonce))
            if existing:return False
            raise RuntimeError('unable to persist federation nonce') from exc
    def _publish_world(self,node_id,data,owner=None):
        if self.world is None:return
        actor=self._owner(owner);self.world.upsert(f'node:{node_id}','device',data.get('name') or node_id,{'node_id':node_id,'platform':data.get('platform','unknown'),'capabilities':data.get('capabilities',[]),'status':data.get('status','ONLINE'),'health':data.get('health',{}),'lease_expires':data.get('lease_expires'),'last_seen':data.get('last_seen',time.time())},owner=actor)
        self.world.relate('NOTSIP','controls',f'node:{node_id}',.95,'federation',owner=actor)
    def register(self,node_id,name,platform,capabilities=None,public_key='',nonce='',signature='',owner=None):
        actor=self._owner(owner)
        if not self.verify(node_id,nonce,signature):raise PermissionError('invalid federation signature')
        if not self._consume_nonce(node_id,nonce):raise PermissionError('replayed federation nonce')
        token=secrets.token_urlsafe(32);now=time.time();self.store.pair_device(node_id,name,platform,public_key,token,owner=actor);data={'owner':actor,'capabilities':capabilities or [],'lease_expires':now+self.lease_seconds,'registered_at':now,'node_epoch':1,'name':name,'platform':platform,'status':'ONLINE','last_seen':now};self.store.exec('UPDATE devices SET data=? WHERE id=?',(json.dumps(data),node_id));self._publish_world(node_id,data,actor);return {'node_id':node_id,'token':token,'lease_seconds':self.lease_seconds,'owner':actor}
    def heartbeat(self,node_id,token,capabilities=None,health=None,nonce='',signature='',owner=None):
        existing=self.store.row('SELECT status FROM devices WHERE id=?',(node_id,))
        if existing and str(existing.get('status','')).upper()=='REVOKED':raise PermissionError('revoked federation node cannot heartbeat')
        if not self.store.device_token_valid(node_id,token):raise PermissionError('invalid node token')
        actor=self.store.device_owner(node_id)
        if not actor:raise PermissionError('federation node ownership is unavailable')
        if owner is not None and str(owner)!=str(actor):raise PermissionError('federation node is not owned by requested actor')
        if not self.verify(node_id,nonce,signature):raise PermissionError('invalid federation signature')
        if not self._consume_nonce(node_id,nonce):raise PermissionError('replayed federation nonce')
        data=self.store.row('SELECT data,status,name,platform,last_seen FROM devices WHERE id=?',(node_id,));cur=json.loads(data['data'] or '{}') if data else {};cur.update({'owner':actor,'capabilities':capabilities or cur.get('capabilities',[]),'health':health or {},'lease_expires':time.time()+self.lease_seconds,'last_heartbeat':time.time(),'status':'ONLINE','name':data.get('name',node_id) if data else node_id,'platform':data.get('platform','unknown') if data else 'unknown','last_seen':time.time()});self.store.exec('UPDATE devices SET last_seen=?,status=?,data=? WHERE id=?',(time.time(),'ONLINE',json.dumps(cur),node_id));self._publish_world(node_id,cur,actor);return cur
    def rotate(self,node_id,owner=None):
        actor=self._require_owner(node_id,owner);token=secrets.token_urlsafe(32);self.store.exec('UPDATE devices SET token_hash=?,status=? WHERE id=?',(hashlib.sha256(token.encode()).hexdigest(),'ONLINE',node_id));return {'node_id':node_id,'token':token,'rotated_at':time.time(),'owner':actor}
    def revoke(self,node_id,owner=None):
        actor=self._require_owner(node_id,owner);self.store.exec("UPDATE devices SET token_hash='',status='REVOKED' WHERE id=?",(node_id,));self._publish_world(node_id,{'name':node_id,'platform':'unknown','capabilities':[],'status':'REVOKED','last_seen':time.time()},actor);return {'node_id':node_id,'status':'REVOKED','owner':actor}
    def reconcile(self,owner=None):
        now=time.time();out=[]
        rows=self.store.devices(owner) if owner is not None else self.store.rows('SELECT id,name,platform,last_seen,status,data FROM devices')
        for r in rows:
            try:d=json.loads(r.get('data') or '{}')
            except (TypeError,ValueError) as exc:raise RuntimeError(f'corrupt federation node metadata for {r.get("id")}') from exc
            actor=str(d.get('owner') or 'primary-user');exp=d.get('lease_expires');status=r['status'] if exp is None else r['status'] if r['status']=='REVOKED' else ('ONLINE' if float(exp)>now else 'STALE')
            if status!=r['status']:self.store.exec('UPDATE devices SET status=? WHERE id=?',(status,r['id']))
            current={'id':r['id'],'status':status,'lease_expires':exp,'capabilities':d.get('capabilities',[]),'name':r.get('name') or r['id'],'platform':r.get('platform') or 'unknown','last_seen':r.get('last_seen'),'owner':actor};self._publish_world(r['id'],current,actor);out.append(current)
        return out
    def recovery_plan(self,owner=None):
        nodes=self.reconcile(owner);return {'generated_at':time.time(),'nodes':nodes,'actions':[{'node':n['id'],'action':'redispatch_or_recover'} for n in nodes if n['status']=='STALE']}
class RecoveryManager:
    def __init__(self,root:Path):self.root=Path(root);self.dir=self.root/'recovery';self.dir.mkdir(parents=True,exist_ok=True)
    def checkpoint(self,state):
        name=f'checkpoint-{int(time.time())}-{uuid.uuid4().hex[:8]}.json';p=self.dir/name;payload=json.dumps(state,indent=2,sort_keys=True);digest=hashlib.sha256(payload.encode()).hexdigest();tmp=p.with_suffix('.tmp');tmp.write_text(payload,encoding='utf-8');tmp.replace(p);side=p.with_suffix('.sha256');tmp_side=side.with_suffix('.tmp');tmp_side.write_text(digest+'  '+name+'\n',encoding='utf-8');tmp_side.replace(side);return str(p.relative_to(self.root))
    def _files(self):return sorted(self.dir.glob('checkpoint-*.json'),key=lambda p:(p.stat().st_mtime,p.name),reverse=True)
    def latest_path(self):files=self._files();return files[0] if files else None
    def _load_verified(self,p):
        raw=p.read_text(encoding='utf-8');side=p.with_suffix('.sha256')
        if not side.exists():raise RuntimeError('recovery checkpoint integrity manifest is missing')
        expected=side.read_text(encoding='utf-8').split()[0].strip().lower();actual=hashlib.sha256(raw.encode()).hexdigest().lower()
        if expected!=actual:raise RuntimeError('recovery checkpoint integrity verification failed')
        return json.loads(raw)
    def latest_verified(self):
        invalid=[]
        for p in self._files():
            try:return p,self._load_verified(p),invalid
            except (OSError,UnicodeError,ValueError,TypeError,json.JSONDecodeError,RuntimeError) as exc:invalid.append({'path':p.name,'reason':str(exc)})
        return None,None,invalid
    def latest(self):p=self.latest_path();return self._load_verified(p) if p else None
    def verify_latest(self):
        files=self._files()
        if not files:return {'valid':False,'reason':'no recovery checkpoint available'}
        p,verified,invalid=self.latest_verified()
        if p is None:return {'valid':False,'reason':('no verified recovery checkpoint is available; '+('; '.join(i['reason'] for i in invalid))) if invalid else 'no verified recovery checkpoint is available','invalid_candidates':invalid}
        return {'valid':True,'path':str(p.relative_to(self.root)),'has_tasks':'tasks' in verified,'has_devices':'devices' in verified,'has_commands':'commands' in verified,'has_world':'world' in verified,'invalid_newer_candidates':invalid}
    def restore_state(self):
        p,state,invalid=self.latest_verified()
        if not p:
            reason='no verified recovery checkpoint is available'
            if invalid:reason='recovery checkpoint integrity verification failed' if any('integrity' in i['reason'] for i in invalid) else reason+'; '+'; '.join(i['reason'] for i in invalid)
            raise RuntimeError(reason)
        verification={'valid':True,'path':str(p.relative_to(self.root)),'invalid_newer_candidates':invalid,'has_tasks':'tasks' in state,'has_devices':'devices' in state,'has_commands':'commands' in state,'has_world':'world' in state}
        return {'status':'RECOVERABLE','state':state,'verification':verification}
