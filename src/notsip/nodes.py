from __future__ import annotations
import hashlib,json,secrets,time,uuid,os
from pathlib import Path
class NodeRegistry:
    def __init__(self,store,secret='',lease_seconds=None): self.store=store; self.secret=secret or ''; self.lease_seconds=int(lease_seconds or os.getenv('NOTSIP_NODE_LEASE_SECONDS','90'))
    def sign(self,node_id,nonce): return hashlib.sha256((self.secret+node_id+nonce).encode()).hexdigest()
    def register(self,node_id,name,platform,capabilities=None,public_key=''):
        token=secrets.token_urlsafe(32); self.store.pair_device(node_id,name,platform,public_key,token); self.store.exec('UPDATE devices SET data=? WHERE id=?',(json.dumps({'capabilities':capabilities or [],'lease_expires':time.time()+self.lease_seconds,'registered_at':time.time()}),node_id)); return {'node_id':node_id,'token':token,'lease_seconds':self.lease_seconds}
    def heartbeat(self,node_id,token,capabilities=None,health=None):
        if not self.store.device_token_valid(node_id,token): raise PermissionError('invalid node token')
        data=self.store.row('SELECT data FROM devices WHERE id=?',(node_id,)); cur=json.loads(data['data'] or '{}') if data else {}; cur.update({'capabilities':capabilities or cur.get('capabilities',[]),'health':health or {},'lease_expires':time.time()+self.lease_seconds,'last_heartbeat':time.time()}); self.store.exec('UPDATE devices SET last_seen=?,status=?,data=? WHERE id=?',(time.time(),'ONLINE',json.dumps(cur),node_id)); return cur
    def reconcile(self):
        now=time.time();out=[]
        for r in self.store.rows('SELECT id,data,status FROM devices'):
            d=json.loads(r['data'] or '{}');exp=d.get('lease_expires',0);status='ONLINE' if exp>now else 'STALE'
            if status!=r['status']:self.store.exec('UPDATE devices SET status=? WHERE id=?',(status,r['id']))
            out.append({'id':r['id'],'status':status,'lease_expires':exp,'capabilities':d.get('capabilities',[])})
        return out
    def recovery_plan(self):
        nodes=self.reconcile();return {'generated_at':time.time(),'nodes':nodes,'actions':[{'node':n['id'],'action':'redispatch_or_recover'} for n in nodes if n['status']=='STALE']}
class RecoveryManager:
    def __init__(self,root:Path):self.root=Path(root);self.dir=self.root/'recovery';self.dir.mkdir(parents=True,exist_ok=True)
    def checkpoint(self,state):p=self.dir/(f'checkpoint-{int(time.time())}-{uuid.uuid4().hex[:8]}.json');p.write_text(json.dumps(state,indent=2,sort_keys=True),encoding='utf-8');return str(p.relative_to(self.root))
    def latest(self):files=sorted(self.dir.glob('checkpoint-*.json'));return json.loads(files[-1].read_text(encoding='utf-8')) if files else None
