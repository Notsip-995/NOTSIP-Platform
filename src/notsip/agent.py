from __future__ import annotations
import inspect,json,re
from datetime import datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from .product_layer import ApprovalStore
from .conversations import ConversationStore
from .execution_gate import ToolExecutionGate

class Agent:
    SYSTEM='''You are NOTSIP, a persistent AI operating layer. Use memory, world state, current time, information, tools and authorization. Never claim external actions succeeded without verified tool output. Never invent devices, accounts, credentials, sensor readings or access. Respect autonomy boundaries. Prefer real tool execution when authorized. State uncertainty clearly.'''
    CITY_TIMEZONES={'tokyo':'Asia/Tokyo','london':'Europe/London','new york':'America/New_York','los angeles':'America/Los_Angeles','paris':'Europe/Paris','berlin':'Europe/Berlin','kigali':'Africa/Kigali','kampala':'Africa/Kampala','nairobi':'Africa/Nairobi','dubai':'Asia/Dubai','singapore':'Asia/Singapore','sydney':'Australia/Sydney'}
    def __init__(self,settings,store,policy,registry,provider,world):
        self.settings=settings;self.store=store;self.policy=policy;self.registry=registry;self.provider=provider;self.world=world;self.user='primary-user';self.approvals=ApprovalStore(Path(settings.data_dir));self.conversations=ConversationStore(Path(settings.data_dir),self.user);self.session=self.conversations.get_or_create();ToolExecutionGate.configure(policy,self.approvals);ToolExecutionGate.wrap_registry(registry)
    @property
    def session_id(self):return self.session['id']
    def new_session(self,title='New conversation'):
        self.session=self.conversations.create(title);return self.session
    def context(self,text):
        now=datetime.now(ZoneInfo(self.settings.local_timezone));return {'time':now.isoformat(),'utc_time':datetime.now(timezone.utc).isoformat(),'timezone':self.settings.local_timezone,'memory':self.store.memories(self.user,text,15),'conversation':self.conversations.history(self.session_id,20),'summary':self.session.get('summary',''),'world':self.world.snapshot(),'pending_approvals':self.approvals.pending()}
    def _time_response(self,text):
        s=text.strip().lower()
        try:local=datetime.now(ZoneInfo(self.settings.local_timezone))
        except ZoneInfoNotFoundError as exc:raise RuntimeError(f'invalid configured timezone: {self.settings.local_timezone}') from exc
        utc=local.astimezone(timezone.utc)
        if s in {'time','date','today','day','what time is it','what date is it','what day is it'} or 'current time' in s or 'current date' in s or 'day of the week' in s:
            return f"It is {local.strftime('%A, %Y-%m-%d %H:%M:%S %Z')} ({self.settings.local_timezone}); UTC is {utc.strftime('%Y-%m-%d %H:%M:%S UTC')}."
        m=re.fullmatch(r'(?:what )?time (?:is it )?(?:in|at) ([a-z][a-z ._-]+)\??',s)
        if m:
            place=m.group(1).strip();tz_name=self.CITY_TIMEZONES.get(place,place if '/' in place else '')
            if not tz_name:return None
            try:tz=ZoneInfo(tz_name)
            except ZoneInfoNotFoundError:return None
            target=utc.astimezone(tz);return f"It is {target.strftime('%A, %Y-%m-%d %H:%M:%S %Z')} in {place.title()}."
        if s in {'tomorrow','what is tomorrow','what date is tomorrow','tomorrow date'}:
            target=local+timedelta(days=1);return f"Tomorrow is {target.strftime('%A, %Y-%m-%d')}."
        return None
    async def handle(self,text):
        self.store.message('user',text);self.conversations.append(self.session_id,'user',text)
        m=re.match(r'^remember(?: that)?\s+(.+)$',text,re.I)
        if m:
            v=m.group(1).strip();self.store.remember(self.user,'semantic',v,.95,'conversation',{'text':text});r=f"I'll remember that: {v}";self.store.message('assistant',r);self.conversations.append(self.session_id,'assistant',r);self.store.audit(self.user,text,'memory','remember','execute',r);return {'response':r,'status':'SUCCESS','session_id':self.session_id}
        time_response=self._time_response(text)
        if time_response:
            self.store.message('assistant',time_response);self.conversations.append(self.session_id,'assistant',time_response);self.store.audit(self.user,text,'time','clock','success',time_response);return {'response':time_response,'status':'SUCCESS','session_id':self.session_id}
        if not self.provider.enabled and not self.provider.fallback_enabled:r=self.fallback(text);self.store.message('assistant',r);self.conversations.append(self.session_id,'assistant',r);self.store.audit(self.user,text,'fallback','agent','respond',r);return {'response':r,'status':'DEGRADED','session_id':self.session_id}
        ctx=self.context(text);msgs=[{'role':'system','content':self.SYSTEM+'\nContext JSON:\n'+json.dumps(ctx,default=str)}]+ctx['conversation'][-12:]+[{'role':'user','content':text}]
        for _ in range(self.settings.max_tool_rounds):
            data=await self.provider.chat(msgs,self.registry.schemas());msg=data['choices'][0]['message'];msgs.append(msg);calls=msg.get('tool_calls') or []
            if not calls:
                r=msg.get('content','');self.store.message('assistant',r);self.conversations.append(self.session_id,'assistant',r);self.store.audit(self.user,text,'model','respond','success',r);return {'response':r,'status':'SUCCESS','session_id':self.session_id}
            for call in calls:
                try:args=json.loads(call['function'].get('arguments') or '{}');res=await self.run_tool(call['function']['name'],args)
                except Exception as e:res={'status':'FAILURE','error':str(e)}
                msgs.append({'role':'tool','tool_call_id':call['id'],'name':call['function']['name'],'content':json.dumps(res,default=str)})
        return {'response':'Agent loop stopped safely after the configured tool rounds.','status':'UNKNOWN','session_id':self.session_id}
    async def run_tool(self,name,args,approved=False):
        tool=self.registry.get(name)
        if not tool:return {'status':'FAILURE','error':'unknown tool'}
        d=self.policy.decide(tool.risk,tool.destructive,tool.capability,approved=approved)
        if not d.allowed:
            if d.needs_confirmation and not approved:
                item=self.approvals.request(name,f'NOTSIP wants to execute {name}',{'tool':name,'args':args,'risk':int(tool.risk),'capability':tool.capability,'required_level':d.required_level})
                self.store.audit(self.user,name,'approval','request','PENDING','approval requested')
                return {'status':'PARTIAL_SUCCESS','approval_required':True,'approval_id':item['id'],'action':name,'reason':d.reason,'capability':d.capability,'required_level':d.required_level}
            return {'status':'FAILURE','approval_required':d.needs_confirmation,'error':d.reason,'capability':d.capability,'required_level':d.required_level}
        invoke_args=dict(args)
        if approved:invoke_args['_notsip_approved']=True
        r=tool.fn(**invoke_args);r=await r if inspect.isawaitable(r) else r;r=r if isinstance(r,dict) else {'status':'SUCCESS','result':r};self.store.audit(self.user,name,name,'execute','SUCCESS',json.dumps(r,default=str));return r
    def fallback(self,text):
        s=text.lower();clock=self._time_response(text)
        if clock:return clock
        if 'what do you remember' in s or 'what do you know about me' in s:
            m=self.store.memories(self.user,'',20);return 'I remember:\n'+'\n'.join('- '+x['content'] for x in m) if m else 'I have no stored memories yet.'
        if 'status' in s:return 'NOTSIP is online. Ask for diagnostics for the detailed capability state.'
        return 'NOTSIP is online in degraded mode. Configure a primary or fallback reasoning provider during setup.'
