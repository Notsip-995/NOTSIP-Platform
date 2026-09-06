from __future__ import annotations
import inspect,json,re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from .product_layer import ApprovalStore

class Agent:
    SYSTEM='''You are NOTSIP, a persistent AI operating layer. Use memory, world state, current time, information, tools and authorization. Never claim external actions succeeded without verified tool output. Never invent devices, accounts, credentials, sensor readings or access. Respect autonomy boundaries. Prefer real tool execution when authorized. State uncertainty clearly.'''
    def __init__(self,settings,store,policy,registry,provider,world):
        self.settings=settings;self.store=store;self.policy=policy;self.registry=registry;self.provider=provider;self.world=world;self.user='primary-user';self.approvals=ApprovalStore(Path(settings.data_dir))
    def context(self,text):
        now=datetime.now(ZoneInfo(self.settings.local_timezone));return {'time':now.isoformat(),'memory':self.store.memories(self.user,text,15),'conversation':self.store.history(20),'world':self.world.snapshot(),'pending_approvals':self.approvals.pending()}
    async def handle(self,text):
        self.store.message('user',text);m=re.match(r'^remember(?: that)?\s+(.+)$',text,re.I)
        if m:
            v=m.group(1).strip();self.store.remember(self.user,'semantic',v,.95,'conversation',{'text':text});r=f"I'll remember that: {v}";self.store.message('assistant',r);self.store.audit(self.user,text,'memory','remember','SUCCESS');return {'response':r,'status':'SUCCESS'}
        if not self.provider.enabled and not self.provider.fallback_enabled:r=self.fallback(text);self.store.message('assistant',r);return {'response':r,'status':'DEGRADED'}
        ctx=self.context(text);msgs=[{'role':'system','content':self.SYSTEM+'\nContext JSON:\n'+json.dumps(ctx,default=str)}]+ctx['conversation'][-12:]+[{'role':'user','content':text}]
        for _ in range(self.settings.max_tool_rounds):
            data=await self.provider.chat(msgs,self.registry.schemas());msg=data['choices'][0]['message'];msgs.append(msg);calls=msg.get('tool_calls') or []
            if not calls:
                r=msg.get('content','');self.store.message('assistant',r);self.store.audit(self.user,text,'model','respond','SUCCESS');return {'response':r,'status':'SUCCESS'}
            for call in calls:
                try:args=json.loads(call['function'].get('arguments') or '{}');res=await self.run_tool(call['function']['name'],args)
                except Exception as e:res={'status':'FAILURE','error':str(e)}
                msgs.append({'role':'tool','tool_call_id':call['id'],'name':call['function']['name'],'content':json.dumps(res,default=str)})
        return {'response':'Agent loop stopped safely after the configured tool rounds.','status':'UNKNOWN'}
    async def run_tool(self,name,args,approved=False):
        tool=self.registry.get(name)
        if not tool:return {'status':'FAILURE','error':'unknown tool'}
        d=self.policy.decide(tool.risk,tool.destructive)
        if not d.allowed:
            if d.needs_confirmation and not approved:
                item=self.approvals.request(name,f'NOTSIP wants to execute {name}',{'tool':name,'args':args,'risk':int(tool.risk)})
                self.store.audit(self.user,name,'approval','request','PENDING')
                return {'status':'PARTIAL_SUCCESS','approval_required':True,'approval_id':item['id'],'action':name,'reason':item['reason']}
            return {'status':'FAILURE','approval_required':d.needs_confirmation,'error':d.reason}
        r=tool.fn(**args);r=await r if inspect.isawaitable(r) else r;r=r if isinstance(r,dict) else {'status':'SUCCESS','result':r};self.store.audit(self.user,name,name,'execute',json.dumps(r,default=str));return r
    def fallback(self,text):
        s=text.lower()
        if s=='time' or 'what time' in s:return 'It is '+datetime.now(ZoneInfo(self.settings.local_timezone)).isoformat()
        if 'what do you remember' in s or 'what do you know about me' in s:
            m=self.store.memories(self.user,'',20);return 'I remember:\n'+'\n'.join('- '+x['content'] for x in m) if m else 'I have no stored memories yet.'
        if 'status' in s:return 'NOTSIP is online. Ask for diagnostics for the detailed capability state.'
        return 'NOTSIP is online in degraded mode. Configure a primary or fallback reasoning provider during setup.'
