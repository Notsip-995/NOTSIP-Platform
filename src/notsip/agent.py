from __future__ import annotations
import json,re,inspect
from datetime import datetime
from zoneinfo import ZoneInfo
class Agent:
    def __init__(self,settings,store,policy,registry,provider,events,workspace,world,jobs):
        self.settings=settings; self.store=store; self.policy=policy; self.registry=registry; self.provider=provider; self.events=events; self.workspace=workspace; self.world=world; self.jobs=jobs; self.user_id='primary-user'
        self.system='''You are NOTSIP, a persistent AI operating layer. NOTSIP is not a generic chatbot. Use memory, world context, information, tools and authorization. Never claim an action succeeded without verified tool output. Never invent devices, credentials, access, people or sensor state. Respect autonomy boundaries. Be concise, observant, and explicit about uncertainty.'''
    def context(self,text):
        local=datetime.now(ZoneInfo(self.settings.local_timezone)); return {'time':{'local':local.isoformat(),'date':local.date().isoformat(),'day':local.strftime('%A'),'timezone':self.settings.local_timezone},'memory':self.store.search_memory(self.user_id,text,12),'conversation':self.store.recent_messages(16),'world':self.world.snapshot(),'devices':self.store.devices()}
    async def handle(self,text):
        self.store.add_message('user',text)
        if re.match(r'^remember(?: that)?\s+',text,re.I):
            content=re.sub(r'^remember(?: that)?\s+','',text,flags=re.I).strip(); self.store.remember(self.user_id,'semantic',content,.95); reply=f"I'll remember that: {content}"; self.store.add_message('assistant',reply); self.store.audit(self.user_id,text,'memory write','memory','remember','SUCCESS'); return {'response':reply,'status':'SUCCESS'}
        if not self.provider.enabled:
            reply=self.fallback(text,self.context(text)); self.store.add_message('assistant',reply); return {'response':reply,'status':'SUCCESS'}
        messages=[{'role':'system','content':self.system+'\nContext:\n'+json.dumps(self.context(text),default=str)},{'role':'user','content':text}]
        for _ in range(self.settings.max_tool_rounds):
            data=await self.provider.chat(messages,self.registry.schemas()); msg=data['choices'][0]['message']; messages.append(msg); calls=msg.get('tool_calls') or []
            if not calls:
                reply=msg.get('content',''); self.store.add_message('assistant',reply); self.store.audit(self.user_id,text,'model response','model','respond','SUCCESS'); return {'response':reply,'status':'SUCCESS'}
            for call in calls:
                name=call['function']['name']; args=json.loads(call['function'].get('arguments') or '{}'); result=await self.run_tool(name,args); messages.append({'role':'tool','tool_call_id':call['id'],'name':name,'content':json.dumps(result,default=str)})
        return {'response':'I stopped the agent loop safely before it could continue.','status':'UNKNOWN'}
    async def run_tool(self,name,args):
        tool=self.registry.get(name)
        if not tool: return {'status':'FAILURE','error':f'Unknown tool: {name}'}
        dec=self.policy.decide(tool.risk,tool.destructive)
        if not dec.allowed: return {'status':'PARTIAL_SUCCESS','approval_required':True,'error':dec.reason}
        try:
            result=tool.fn(**args); result=await result if inspect.isawaitable(result) else result; result=result if isinstance(result,dict) else {'status':'SUCCESS','result':result}; self.store.audit(self.user_id,name,'tool execution',name,'execute',json.dumps(result,default=str)); return result
        except Exception as e:
            self.store.audit(self.user_id,name,'tool error',name,'execute',str(e)); return {'status':'FAILURE','error':str(e)}
    def fallback(self,text,ctx):
        s=text.lower()
        if ('what time' in s or s=='time'): return f"It is {ctx['time']['local']} ({ctx['time']['day']})."
        if 'what do you remember' in s or 'what do you know about me' in s:
            m=self.store.search_memory(self.user_id,'',20); return 'I remember:\n'+'\n'.join('- '+x['content'] for x in m) if m else 'I do not have stored personal memories yet.'
        return 'NOTSIP is online, but its reasoning model is not configured. Connect a local or cloud OpenAI-compatible model in .env.'
