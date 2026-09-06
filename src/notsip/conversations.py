from __future__ import annotations
import json,time,uuid
from pathlib import Path

class ConversationStore:
    def __init__(self,root,user_id='primary-user'):
        self.path=Path(root)/'runtime'/'conversations.json';self.path.parent.mkdir(parents=True,exist_ok=True);self.user_id=user_id
    def _load(self):
        try:return json.loads(self.path.read_text(encoding='utf-8'))
        except Exception:return {'sessions':{}}
    def _save(self,d):
        t=self.path.with_suffix('.tmp');t.write_text(json.dumps(d,sort_keys=True,ensure_ascii=False));t.replace(self.path)
    def create(self,title='New conversation'):
        d=self._load();sid=uuid.uuid4().hex;d['sessions'][sid]={'id':sid,'user_id':self.user_id,'title':title,'created':time.time(),'updated':time.time(),'summary':'','messages':[]};self._save(d);return d['sessions'][sid]
    def get_or_create(self,sid=''):
        d=self._load()
        if sid and sid in d['sessions']:return d['sessions'][sid]
        return self.create()
    def append(self,sid,role,content):
        d=self._load();s=d['sessions'].setdefault(sid,{'id':sid,'user_id':self.user_id,'title':'Conversation','created':time.time(),'updated':time.time(),'summary':'','messages':[]});s['messages'].append({'role':role,'content':content,'ts':time.time()});s['updated']=time.time();self._save(d);return s
    def history(self,sid,limit=20):
        d=self._load();s=d['sessions'].get(sid,{});return s.get('messages',[])[-limit:]
    def list(self):
        d=self._load();return sorted([{k:v for k,v in s.items() if k!='messages'} for s in d['sessions'].values()],key=lambda x:x.get('updated',0),reverse=True)
    def summarize(self,sid,summary):
        d=self._load();s=d['sessions'].get(sid)
        if not s:return None
        s['summary']=summary;s['updated']=time.time();self._save(d);return s
