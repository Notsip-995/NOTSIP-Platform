from __future__ import annotations
import json,time,uuid,threading
from pathlib import Path

class ConversationStore:
    _lock=threading.RLock()
    def __init__(self,root,user_id='primary-user'):
        self.path=Path(root)/'runtime'/'conversations.json';self.path.parent.mkdir(parents=True,exist_ok=True);self.user_id=user_id
    def _load(self):
        try:return json.loads(self.path.read_text(encoding='utf-8'))
        except Exception:return {'sessions':{}}
    def _save(self,d):
        t=self.path.with_suffix('.tmp');t.write_text(json.dumps(d,sort_keys=True,ensure_ascii=False));t.replace(self.path)
    def _owned(self,s):
        return bool(s and s.get('user_id')==self.user_id)
    def create(self,title='New conversation'):
        with self._lock:
            d=self._load();sid=uuid.uuid4().hex;d['sessions'][sid]={'id':sid,'user_id':self.user_id,'title':title,'created':time.time(),'updated':time.time(),'summary':'','messages':[]};self._save(d);return d['sessions'][sid]
    def get_or_create(self,sid=''):
        with self._lock:
            d=self._load()
            if sid and self._owned(d['sessions'].get(sid)):
                return d['sessions'][sid]
            candidates=[s for s in d['sessions'].values() if self._owned(s)]
            if candidates:
                return max(candidates,key=lambda s:s.get('updated',0))
            return self.create()
    def append(self,sid,role,content):
        with self._lock:
            d=self._load();s=d['sessions'].get(sid)
            if s is not None and not self._owned(s):
                raise PermissionError('conversation does not belong to this user')
            if s is None:
                s={'id':sid,'user_id':self.user_id,'title':'Conversation','created':time.time(),'updated':time.time(),'summary':'','messages':[]};d['sessions'][sid]=s
            s['messages'].append({'role':role,'content':content,'ts':time.time()});s['updated']=time.time();self._save(d);return s
    def history(self,sid,limit=20):
        with self._lock:
            d=self._load();s=d['sessions'].get(sid)
            if not self._owned(s):return []
            return s.get('messages',[])[-limit:]
    def list(self):
        with self._lock:
            d=self._load();return sorted([{k:v for k,v in s.items() if k!='messages'} for s in d['sessions'].values() if self._owned(s)],key=lambda x:x.get('updated',0),reverse=True)
    def summarize(self,sid,summary):
        with self._lock:
            d=self._load();s=d['sessions'].get(sid)
            if not self._owned(s):return None
            s['summary']=summary;s['updated']=time.time();self._save(d);return s
