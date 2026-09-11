from __future__ import annotations
import inspect,json,re,threading
from datetime import datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from .product_layer import ApprovalStore
from .conversations import ConversationStore
from .execution_gate import ToolExecutionGate
from .user_profile import UserProfileStore
from .actor_context import current_actor
from .policy import Risk

class Agent:
    SYSTEM='''You are NOTSIP, a persistent AI operating layer. Use memory, world state, current time, user profile, information, tools and authorization. Never claim external actions succeeded without verified tool output. Never invent devices, accounts, credentials, sensor readings or access. Respect autonomy boundaries. State uncertainty clearly.'''
    CITY_TIMEZONES={'tokyo':'Asia/Tokyo','london':'Europe/London','new york':'America/New_York','los angeles':'America/Los_Angeles','paris':'Europe/Paris','berlin':'Europe/Berlin','kigali':'Africa/Kigali','kampala':'Africa/Kampala','nairobi':'Africa/Nairobi','dubai':'Asia/Dubai','singapore':'Asia/Singapore','sydney':'Australia/Sydney'}
    WEEKDAYS={'monday':0,'tuesday':1,'wednesday':2,'thursday':3,'friday':4,'saturday':5,'sunday':6}
    def __init__(self,settings,store,policy,registry,provider,world):
        self.settings=settings;self.store=store;self.policy=policy;self.registry=registry;self.provider=provider;self.world=world;self.approvals=ApprovalStore(Path(settings.data_dir));self._conversation_stores={};self._profile_stores={};self._session_ids={};self._store_lock=threading.RLock();ToolExecutionGate.configure(policy,self.approvals);ToolExecutionGate.wrap_registry(registry)
    @property
    def user(self):return current_actor()
    def _conversation_store(self):
        uid=self.user
        with self._store_lock:return self._conversation_stores.setdefault(uid,ConversationStore(Path(self.settings.data_dir),uid))
    @property
    def conversations(self):return self._conversation_store()
    @property
    def profile(self):
        uid=self.user
        with self._store_lock:return self._profile_stores.setdefault(uid,UserProfileStore(Path(self.settings.data_dir),uid))
    @property
    def session(self):
        store=self._conversation_store();sid=self._session_ids.get(self.user,'');return store.get_or_create(sid)
    @session.setter
    def session(self,value):self._session_ids[self.user]=str((value or {}).get('id',''))
    @property
    def session_id(self):return self.session['id']
    def new_session(self,title='New conversation'):
        s=self._conversation_store().create(title);self.session=s;return s
    def context(self,text):
        now=datetime.now(ZoneInfo(self.settings.local_timezone));session=self.session;store=self._conversation_store();return {'actor':self.user,'time':now.isoformat(),'utc_time':datetime.now(timezone.utc).isoformat(),'timezone':self.settings.local_timezone,'user_profile':self.profile.load(),'memory':self.store.memories(self.user,text,15),'conversation':store.history(session['id'],20),'summary':session.get('summary',''),'world':self.world.snapshot(),'pending_approvals':[x for x in self.approvals.pending() if (x.get('context') or {}).get('actor','primary-user')==self.user]}
    def _time_response(self,text):
        s=text.strip().lower()
        try:local=datetime.now(ZoneInfo(self.settings.local_timezone))
        except ZoneInfoNotFoundError as exc:raise RuntimeError(f'invalid configured timezone: {self.settings.local_timezone}') from exc
        utc=local.astimezone(timezone.utc)
        if s in {'time','date','today','day','what time is it','what date is it','what day is it'} or 'current time' in s or 'current date' in s or 'day of the week' in s:return f"It is {local.strftime('%A, %Y-%m-%d %H:%M:%S %Z')} ({self.settings.local_timezone}); UTC is {utc.strftime('%Y-%m-%d %H:%M:%S UTC')}."
        m=re.fullmatch(r'(?:what )?time (?:is it )?(?:in|at) ([a-z][a-z ._-]+)\??',s)
        if m:
            place=m.group(1).strip();tz_name=self.CITY_TIMEZONES.get(place,place if '/' in place else '')
            if not tz_name:return None
            try:tz=ZoneInfo(tz_name)
            except ZoneInfoNotFoundError:return None
            target=utc.astimezone(tz);return f"It is {target.strftime('%A, %Y-%m-%d %H:%M:%S %Z')} in {place.title()}."
        if s in {'tomorrow','what is tomorrow','what date is tomorrow','tomorrow date'}:target=local+timedelta(days=1);return f"Tomorrow is {target.strftime('%A, %Y-%m-%d')}."
        if s in {'yesterday','what was yesterday','what date was yesterday'}:target=local-timedelta(days=1);return f"Yesterday was {target.strftime('%A, %Y-%m-%d')}."
        if s in {'tonight','what is tonight'}:return f"Tonight is {local.strftime('%A, %Y-%m-%d')} in {self.settings.local_timezone}."
        m=re.fullmatch(r'(?:what is |what date is )?next (monday|tuesday|wednesday|thursday|friday|saturday|sunday)\??',s)
        if m:
            delta=(self.WEEKDAYS[m.group(1)]-local.weekday())%7 or 7;target=local+timedelta(days=delta);return f"Next {m.group(1).title()} is {target.strftime('%A, %Y-%m-%d')}."
        m=re.fullmatch(r'(?:what was |what date was )?last (monday|tuesday|wednesday|thursday|friday|saturday|sunday)\??',s)
        if m:
            delta=(local.weekday()-self.WEEKDAYS[m.group(1)])%7 or 7;target=local-timedelta(days=delta);return f"Last {m.group(1).title()} was {target.strftime('%A, %Y-%m-%d')}."
        if s in {'in two weeks','two weeks from now','what date is in two weeks'}:target=local+timedelta(weeks=2);return f"In two weeks it will be {target.strftime('%A, %Y-%m-%d')}."
        return None
    async def handle(self,text):
        store=self._conversation_store();session=self.session;store.append(session['id'],'user',text)
        m=re.match(r'^remember(?: that)?\s+(.+)$',text,re.I)
        if m:
            v=m.group(1).strip();self.store.remember(self.user,'semantic',v,.95,'conversation',{'text':text});r=f"I'll remember that: {v}";store.append(session['id'],'assistant',r);self.store.audit(self.user,text,'memory','remember','execute',r);return {'response':r,'status':'SUCCESS','session_id':session['id'],'actor':self.user}
        m=re.match(r'^(?:call me|my name is)\s+(.+)$',text,re.I)
        if m:
            name=m.group(1).strip().rstrip('.');self.profile.update(preferred_name=name,identity={'preferred_name':name});r=f"Understood. I'll call you {name}.";store.append(session['id'],'assistant',r);self.store.audit(self.user,text,'profile','update','success',r);return {'response':r,'status':'SUCCESS','session_id':session['id'],'actor':self.user}
        time_response=self._time_response(text)
        if time_response:
            store.append(session['id'],'assistant',time_response);self.store.audit(self.user,text,'time','clock','success',time_response);return {'response':time_response,'status':'SUCCESS','session_id':session['id'],'actor':self.user}
        if not self.provider.enabled and not self.provider.fallback_enabled:
            r=self.fallback(text);store.append(session['id'],'assistant',r);self.store.audit(self.user,text,'fallback','agent','respond',r);return {'response':r,'status':'DEGRADED','session_id':session['id'],'actor':self.user}
        ctx=self.context(text);msgs=[{'role':'system','content':self.SYSTEM+'\nContext JSON:\n'+json.dumps(ctx,default=str)}]+ctx['conversation'][-12:]+[{'role':'user','content':text}]
        for _ in range(self.settings.max_tool_rounds):
            data=await self.provider.chat(msgs,self.registry.schemas());msg=data['choices'][0]['message'];msgs.append(msg);calls=msg.get('tool_calls') or []
            if not calls:
                r=msg.get('content','');store.append(session['id'],'assistant',r);self.store.audit(self.user,text,'model','respond','success',r);return {'response':r,'status':'SUCCESS','session_id':session['id'],'actor':self.user}
            for call in calls:
                try:args=json.loads(call['function'].get('arguments') or '{}');res=await self.run_tool(call['function']['name'],args)
                except Exception as e:res={'status':'FAILURE','error':str(e)}
                msgs.append({'role':'tool','tool_call_id':call['id'],'name':call['function']['name'],'content':json.dumps(res,default=str)})
        return {'response':'Agent loop stopped safely after the configured tool rounds.','status':'UNKNOWN','session_id':session['id'],'actor':self.user}
    async def run_tool(self,name,args):
        tool=self.registry.get(name)
        if not tool:return {'status':'FAILURE','error':'unknown tool'}
        if self.user=='voice:unverified' and tool.risk>=Risk.HIGH:return {'status':'FAILURE','error':'verified speaker identity is required for high-risk actions','capability':tool.capability,'required_level':int(tool.risk)}
        d=self.policy.decide(tool.risk,tool.destructive,tool.capability,approved=False)
        if not d.allowed:
            if d.needs_confirmation:
                item=self.approvals.request(name,f'NOTSIP wants to execute {name}',{'tool':name,'args':args,'risk':int(tool.risk),'capability':tool.capability,'required_level':d.required_level,'actor':self.user});self.store.audit(self.user,name,'approval','request','PENDING','approval requested');return {'status':'PARTIAL_SUCCESS','approval_required':True,'approval_id':item['id'],'action':name,'reason':d.reason,'capability':d.capability,'required_level':d.required_level}
            return {'status':'FAILURE','approval_required':False,'error':d.reason,'capability':d.capability,'required_level':d.required_level}
        r=tool.fn(**args);r=await r if inspect.isawaitable(r) else r;r=r if isinstance(r,dict) else {'status':'SUCCESS','result':r};self.store.audit(self.user,name,name,'execute',str(r.get('status','SUCCESS')),json.dumps(r,default=str));return r
    async def run_approved_tool(self,approval_id):
        item=self.approvals._load().get(str(approval_id));actor=self.user
        if not item or str((item.get('context') or {}).get('actor') or 'primary-user')!=actor:return {'status':'FAILURE','error':'approval not found for current actor'}
        if item.get('status')!='APPROVED':return {'status':'FAILURE','error':f"approval is {item.get('status','unknown')}"}
        name=str((item.get('context') or {}).get('tool') or '');args=(item.get('context') or {}).get('args') or {}
        if not name or not isinstance(args,dict):return {'status':'FAILURE','error':'invalid approved tool context'}
        tool=self.registry.get(name)
        if not tool:return {'status':'FAILURE','error':'approved tool no longer exists'}
        if not getattr(tool,'_notsip_guarded',False):return {'status':'FAILURE','error':'approved tool is not protected by the central execution gate'}
        result=tool.fn(**args)
        if inspect.isawaitable(result):result=await result
        return result if isinstance(result,dict) else {'status':'SUCCESS','result':result}
    def fallback(self,text):
        s=text.lower();clock=self._time_response(text)
        if clock:return clock
        if 'what do you remember' in s or 'what do you know about me' in s:
            p=self.profile.load();m=self.store.memories(self.user,'',20);lines=[]
            if p.get('preferred_name'):lines.append(f"Preferred name: {p['preferred_name']}")
            lines.extend('- '+x['content'] for x in m);return 'I remember:\n'+'\n'.join(lines) if lines else 'I have no stored memories yet.'
        if 'status' in s:return 'NOTSIP is online. Ask for diagnostics for the detailed capability state.'
        return 'NOTSIP is online in degraded mode. Configure a primary or fallback reasoning provider during setup.'
