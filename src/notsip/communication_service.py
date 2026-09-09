from __future__ import annotations
import re,time
from pathlib import Path
from .actor_context import current_actor
from .user_profile import UserProfileStore

class CommunicationService:
    def __init__(self,profile,store,data_dir=None):self.profile=profile;self.store=store;self.data_dir=Path(data_dir or getattr(profile,'root','.')).resolve()
    def _profile_for_actor(self):
        actor=current_actor()
        if actor=='primary-user' and getattr(self.profile,'user_id','primary-user')=='primary-user':return self.profile
        return UserProfileStore(self.data_dir,actor)
    def contact(self,name):
        needle=' '.join(str(name or '').lower().split())
        if not needle:raise ValueError('contact name is required')
        people=self._profile_for_actor().load().get('important_people') or {}
        exact=next((v for k,v in people.items() if ' '.join(str(k).lower().split())==needle),None)
        if exact is None:raise LookupError(f'contact not found: {name}')
        if not isinstance(exact,dict):raise ValueError('contact record must be an object')
        return exact
    def contacts(self):return self._profile_for_actor().load().get('important_people') or {}
    def _android(self):
        rows=self.store.devices();online=[r for r in rows if str(r.get('platform','')).lower()=='android' and r.get('status')=='ONLINE']
        if not online:raise RuntimeError('no online authorized Android device is available')
        return online[0]
    def sms(self,name,text,device_id=''):
        person=self.contact(name);number=str(person.get('phone') or person.get('mobile') or '').strip()
        if not number:raise ValueError(f'contact has no phone number: {name}')
        if not re.fullmatch(r'[+0-9][0-9 .()\-]{4,30}',number):raise ValueError('contact phone number has invalid format')
        target=device_id or self._android()['id'];result=self.store.queue_command(target,'send_sms',{'number':number,'text':str(text)});return {'status':'QUEUED','channel':'sms','contact':name,'command_id':result,'device_id':target,'verified':False,'note':'SMS was queued on the authorized Android device; carrier delivery was not independently verified.'}
    def notify(self,name,text,device_id=''):
        person=self.contact(name);target=device_id or self._android()['id'];result=self.store.queue_command(target,'notify',{'text':str(text),'contact':name});return {'status':'QUEUED','channel':'notification','contact':name,'command_id':result,'device_id':target,'verified':False,'note':'Notification was queued on the authorized Android device; presentation was not independently verified.','recipient_metadata':{'name':name,'has_email':bool(person.get('email')),'has_phone':bool(person.get('phone') or person.get('mobile'))},'queued_at':time.time()}
