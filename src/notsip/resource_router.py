from __future__ import annotations
import json,time
from .actor_context import current_actor

class ResourceRouter:
    """Select healthy, leased and actor-authorized local/remote resources without changing identity."""
    def __init__(self, store): self.store=store
    def snapshot(self,owner=None):
        actor=current_actor() if owner is None else str(owner)
        nodes=[]
        for row in self.store.devices(actor):
            data=json.loads(row.get('data') or '{}');lease_expires=data.get('lease_expires');status=row['status']
            if status!='REVOKED' and lease_expires is not None and float(lease_expires)<=time.time():status='STALE'
            nodes.append({'id':row['id'],'name':row['name'],'platform':row['platform'],'status':status,'capabilities':data.get('capabilities',[]),'health':data.get('health',{}),'location':data.get('location'),'permissions':data.get('permissions',[]),'lease_expires':lease_expires,'owner':actor})
        return nodes
    def select(self, capability, *, prefer_local=True, owner=None):
        nodes=[n for n in self.snapshot(owner) if n['status']=='ONLINE' and capability in set(n['capabilities'])]
        if prefer_local:nodes.sort(key=lambda n:(0 if n['platform'].lower() in {'local','windows','linux','darwin'} else 1,n['id']))
        if not nodes:return {'status':'BLOCKED_BY_EXTERNAL_ENVIRONMENT','error':f'no online authorized node provides {capability}','capability':capability,'owner':owner or current_actor()}
        return {'status':'SUCCESS','node':nodes[0]}

class RobotGateway:
    REQUIRED={'status','sensors','power','navigation','control','communication','diagnostics','safety'}
    def __init__(self,store,router=None):self.store=store;self.router=router or ResourceRouter(store)
    def _placeholder(self):return '%s' if getattr(self.store,'_backend',None) else '?'
    def _require_owner(self,node_id,owner=None):
        actor=current_actor() if owner is None else str(owner)
        if not self.store.device_owned_by(node_id,actor):raise PermissionError('robot node is not owned by current actor')
        return actor
    def register_schema(self,node_id,capabilities,*,location=None,permissions=None,owner=None):
        actor=self._require_owner(node_id,owner);p=self._placeholder();row=self.store.row(f'SELECT id,data FROM devices WHERE id={p}',(node_id,))
        if not row:raise KeyError(node_id)
        data=json.loads(row.get('data') or '{}');data.update({'robot_capabilities':sorted(set(capabilities or [])),'location':location,'permissions':permissions or [],'owner':actor});self.store.exec(f'UPDATE devices SET data={p} WHERE id={p}',(json.dumps(data),node_id));return data
    def status(self,node_id,owner=None):
        actor=self._require_owner(node_id,owner);p=self._placeholder();row=self.store.row(f'SELECT id,name,platform,status,data,last_seen FROM devices WHERE id={p}',(node_id,))
        if not row:raise KeyError(node_id)
        data=json.loads(row.get('data') or '{}');lease_expires=data.get('lease_expires');status=row['status']
        if status!='REVOKED' and lease_expires is not None and float(lease_expires)<=time.time():status='STALE'
        health=data.get('health',{});return {'id':row['id'],'name':row['name'],'platform':row['platform'],'status':status,'last_seen':row['last_seen'],'lease_expires':lease_expires,'robot_capabilities':data.get('robot_capabilities',[]),'sensors':health.get('sensors',{}),'power':health.get('power'),'navigation':health.get('navigation'),'diagnostics':health.get('diagnostics'),'safety':health.get('safety'),'owner':actor,'generated_at':time.time()}
    def command(self,node_id,action,payload=None,owner=None):
        actor=self._require_owner(node_id,owner);st=self.status(node_id,actor)
        if st['status']!='ONLINE':return {'status':'FAILURE','error':'robot node is not online'}
        if 'control' not in st['robot_capabilities']:return {'status':'FAILURE','error':'robot control capability is not authorized'}
        if st.get('safety') is False:return {'status':'FAILURE','error':'robot safety state does not permit control'}
        cid=self.store.queue_command(node_id,action,payload or {});return {'status':'QUEUED','command_id':cid,'node_id':node_id,'action':action,'owner':actor}
