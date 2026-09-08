from __future__ import annotations
import json,time

class ResourceRouter:
    """Select healthy authorized local/remote resources without changing identity."""
    def __init__(self, store): self.store=store
    def snapshot(self):
        nodes=[]
        for row in self.store.rows('SELECT id,name,platform,status,data FROM devices'):
            data=json.loads(row.get('data') or '{}')
            nodes.append({'id':row['id'],'name':row['name'],'platform':row['platform'],'status':row['status'],'capabilities':data.get('capabilities',[]),'health':data.get('health',{}),'location':data.get('location'),'permissions':data.get('permissions',[])})
        return nodes
    def select(self, capability, *, prefer_local=True):
        nodes=[n for n in self.snapshot() if n['status']=='ONLINE' and capability in set(n['capabilities'])]
        if prefer_local:
            nodes.sort(key=lambda n:(0 if n['platform'].lower() in {'local','windows','linux','darwin'} else 1, n['id']))
        if not nodes:return {'status':'BLOCKED_BY_EXTERNAL_ENVIRONMENT','error':f'no online authorized node provides {capability}','capability':capability}
        return {'status':'SUCCESS','node':nodes[0]}

class RobotGateway:
    REQUIRED={'status','sensors','power','navigation','control','communication','diagnostics','safety'}
    def __init__(self, store, router=None): self.store=store; self.router=router or ResourceRouter(store)
    def register_schema(self, node_id, capabilities, *, location=None, permissions=None):
        row=self.store.row('SELECT id,data FROM devices WHERE id=?',(node_id,))
        if not row:raise KeyError(node_id)
        data=json.loads(row.get('data') or '{}');data.update({'robot_capabilities':sorted(set(capabilities or [])),'location':location,'permissions':permissions or []});self.store.exec('UPDATE devices SET data=? WHERE id=?',(json.dumps(data),node_id));return data
    def status(self,node_id):
        row=self.store.row('SELECT id,name,platform,status,data,last_seen FROM devices WHERE id=?',(node_id,))
        if not row:raise KeyError(node_id)
        data=json.loads(row.get('data') or '{}');return {'id':row['id'],'name':row['name'],'platform':row['platform'],'status':row['status'],'last_seen':row['last_seen'],'robot_capabilities':data.get('robot_capabilities',[]),'sensors':data.get('health',{}).get('sensors',{}),'power':data.get('health',{}).get('power'),'navigation':data.get('health',{}).get('navigation'),'diagnostics':data.get('health',{}).get('diagnostics'),'safety':data.get('health',{}).get('safety'),'generated_at':time.time()}
    def command(self,node_id,action,payload=None):
        st=self.status(node_id)
        if st['status']!='ONLINE':return {'status':'FAILURE','error':'robot node is not online'}
        if 'control' not in st['robot_capabilities']:return {'status':'FAILURE','error':'robot control capability is not authorized'}
        cid=self.store.queue_command(node_id,action,payload or {});return {'status':'QUEUED','command_id':cid,'node_id':node_id,'action':action}
