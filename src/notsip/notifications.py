from __future__ import annotations
import hashlib,json,threading,time,uuid
from pathlib import Path
from .actor_context import set_actor,reset_actor

class NotificationStore:
    def __init__(self,root,device_store=None,cooldown=900):
        self.path=Path(root)/'runtime'/'notifications.json';self.path.parent.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock();self.device_store=device_store;self.cooldown=max(60,int(cooldown))
    def _load(self):
        try:return json.loads(self.path.read_text(encoding='utf-8'))
        except Exception:return {}
    def _save(self,data):
        tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2,sort_keys=True),encoding='utf-8');tmp.replace(self.path)
    def create(self,actor,title,body,priority='IMPORTANT',reason='',source='intelligence',dedupe_key=''):
        actor=str(actor or 'primary-user').strip() or 'primary-user';dedupe=dedupe_key or f'{actor}:{title}:{body}'
        key=hashlib.sha256(dedupe.encode()).hexdigest();now=time.time()
        with self.lock:
            data=self._load();existing=data.get(key)
            if existing and now-float(existing.get('created_at',0))<self.cooldown:
                existing['last_seen']=now;self._save(data);return existing
            item={'id':uuid.uuid4().hex,'actor':actor,'title':str(title),'body':str(body),'priority':str(priority),'reason':str(reason),'source':str(source),'created_at':now,'last_seen':now,'acknowledged':False,'dedupe_key':key}
            data[key]=item;self._save(data)
        if self.device_store is not None:
            token=set_actor(actor)
            try:
                for device in self.device_store.devices(actor):
                    try:self.device_store.queue_command(device['id'],'notify',{'title':item['title'],'body':item['body'],'priority':item['priority'],'notification_id':item['id']})
                    except Exception:item.setdefault('delivery_errors',[]).append(device['id'])
            finally:reset_actor(token)
        return item
    def list(self,actor='primary-user',include_ack=False,limit=100):
        actor=str(actor or 'primary-user').strip() or 'primary-user';now=time.time()
        with self.lock:
            items=[x for x in self._load().values() if x.get('actor')==actor and (include_ack or not x.get('acknowledged'))]
        items.sort(key=lambda x:(float(x.get('created_at',0)),str(x.get('id',''))),reverse=True);return items[:max(1,min(int(limit),500))]
    def acknowledge(self,actor,notification_id):
        actor=str(actor or 'primary-user').strip() or 'primary-user'
        with self.lock:
            data=self._load()
            for key,item in data.items():
                if item.get('actor')==actor and item.get('id')==notification_id:
                    item['acknowledged']=True;item['acknowledged_at']=time.time();self._save(data);return item
        return None
