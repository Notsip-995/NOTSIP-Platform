from __future__ import annotations
import json,time

class ResourceRouter:
    """Select healthy, leased and authorized local/remote resources without changing identity."""
    def __init__(self, store): self.store=store
    def snapshot(self):
        now=time.time();nodes=[]
        for row in self.store.rows('SELECT id,name,platform,status,data FROM devices'):
            data=json.loads(row.get('data') or '{}');lease_expires=data.get('lease_expires')
            status=row['status']
            if status!='REVOKED' and lease_expires is not None and float(lease_expires)<=now:status='STALE'
            nodes.append({'id':row['id'],'name':row['name'],'platform':row['platform'],'status':status,'capabilities':data.get('capabilities',[]),'health':data.get('health',{}),'location':data.get('location'),'permissions':data.get('permissions',[]),'lease_expires':lease_expires})
        return nodes
    def select(self, capability, *, prefer_local=True):
        nodes=[n for n in self.snapshot() if n['status']=='ONLINE' and capability in set(n['capabilities'])]
        if prefer_local:nodes.sort(key=lambda n:(0 if n['platform'].lower() in {'local','windows','linux','darwin'} else 1,n['id']))
        if not nodes:return {'status':'BLOCKED_BY_EXTERNAL_ENVIRONMENT','error':f'no online authorized node provides {capability}','capability':capability}
        return {'status':'SUCCESS','node':nodes[0]}

class RobotGateway:
    REQUIRED={'status','sensors','power','navigation','control','communication','diagnostics','safety'}
    def __init__(self,store,router=None):self.store=store;self.router=router or ResourceRouter(store)
    def register_schema(self,node_id,capabilities,*,location=None,permissions=None):
        row=self.store.row('SELECT id,data FROM devices WHERE id=?',(node_id,))
        if not row:raise KeyError(node_id)
        data=json.loads(row.get('data') or '{}');data.update({'robot_capabilities':sorted(set(capabilities or [])),'location':location,'permissions':permissions or []});self.store.exec('UPDATE devices SET data=? WHERE id=?',(json.dumps(data),node_id));return data
    def status(self,node_id):
        row=self.store.row('SELECT id,name,platform,status,data,last_seen FROM devices WHERE id=?',(node_id,))
        if not row:raise KeyError(node_id)
        data=json.loads(row.get('data') or '{}');lease_expires=data.get('lease_expires');status=row['status']
        if status!='REVOKED' and lease_expires is not None and float(lease_expires)<=time.time():status='STALE'
        health=data.get('health',{});return {'id':row['id'],'name':row['name'],'platform':row['platform'],'status':status,'last_seen':row['last_seen'],'lease_expires':lease_expires,'robot_capabilities':data.get('robot_capabilities',[]),'sensors':health.get('sensors',{}),'power':health.get('power'),'navigation':health.get('navigation'),'diagnostics':health.get('diagnostics'),'safety':health.get('safety'),'generated_at':time.time()}
    def command(self,node_id,action,payload=None):
        st=self.status(node_id)
        if st['status']!='ONLINE':return {'status':'FAILURE','error':'robot node is not online'}
        if 'control' not in st['robot_capabilities']:return {'status':'FAILURE','error':'robot control capability is not authorized'}
        if st.get('safety') is False:return {'status':'FAILURE','error':'robot safety state does not permit control'}
        cid=self.store.queue_command(node_id,action,payload or {});return {'status':'QUEUED','command_id':cid,'node_id':node_id,'action':action}
