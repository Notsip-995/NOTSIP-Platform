from __future__ import annotations
import hashlib,json,threading,time
from pathlib import Path

FIELDS=('identity','preferred_name','communication_style','preferences','routines','important_people','projects','devices','accounts','locations','schedules','frequently_used_services','permissions','long_term_objectives')

class UserProfileStore:
    """Durable non-secret user model kept separate from LLM conversation context."""
    def __init__(self, root: Path, user_id='primary-user'):
        self.root=Path(root).resolve();self.user_id=str(user_id).strip() or 'primary-user';self.lock=threading.RLock();self.root.mkdir(parents=True,exist_ok=True)
        if self.user_id=='primary-user':self.path=self.root/'user-profile-primary-user.json'
        else:
            digest=hashlib.sha256(self.user_id.encode('utf-8')).hexdigest()[:24]
            self.path=self.root/'profiles'/f'{digest}.json'
        self.path.parent.mkdir(parents=True,exist_ok=True)
    def _default(self):
        return {'user_id':self.user_id,'identity':{},'preferred_name':'','communication_style':'concise','preferences':{},'routines':{},'important_people':{},'projects':{},'devices':{},'accounts':{},'locations':{},'schedules':{},'frequently_used_services':{},'permissions':{},'long_term_objectives':[],'updated_at':time.time()}
    def load(self):
        with self.lock:
            if not self.path.exists():return self._default()
            try:data=json.loads(self.path.read_text(encoding='utf-8'))
            except Exception as exc:raise RuntimeError(f'user profile is unreadable: {exc}') from exc
            if not isinstance(data,dict):raise RuntimeError('user profile is structurally invalid')
            stored_user=str(data.get('user_id') or '').strip() or 'primary-user'
            if stored_user!=self.user_id:raise PermissionError('user profile ownership mismatch')
            base=self._default();base.update({k:v for k,v in data.items() if k in FIELDS or k in {'user_id','updated_at'}});return base
    def save(self, profile):
        data=self.load()
        for key in FIELDS:
            if key in profile:data[key]=profile[key]
        data['updated_at']=time.time();tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(data,sort_keys=True,indent=2,default=str),encoding='utf-8');tmp.replace(self.path);return data
    def update(self, **changes):
        valid={k:v for k,v in changes.items() if k in FIELDS}
        if 'preferred_name' in valid:valid['preferred_name']=str(valid['preferred_name']).strip()
        return self.save(valid)
    def set_preference(self,key,value):
        data=self.load();prefs=dict(data.get('preferences') or {});prefs[str(key)]=value;return self.save({'preferences':prefs})
    def add_person(self,name,data=None):
        profile=self.load();people=dict(profile.get('important_people') or {});people[str(name)]=data or {};return self.save({'important_people':people})
    def add_project(self,name,data=None):
        profile=self.load();projects=dict(profile.get('projects') or {});projects[str(name)]=data or {};return self.save({'projects':projects})
