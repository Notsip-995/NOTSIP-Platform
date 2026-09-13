from __future__ import annotations
from fastapi import Depends,HTTPException
from .policy import Risk
from .tools import Tool

def attach(app,require_auth,agent,browser,registry):
    if registry.get('browser_interact') is None:
        async def browser_interact(url,actions,wait_ms=300):
            actions=list(actions or [])
            if not actions:raise ValueError('at least one browser action is required')
            if len(actions)>25:raise ValueError('browser workflow exceeds 25 actions')
            return await browser.interact(str(url),actions,max(50,min(int(wait_ms),5000)))
        registry.add(Tool('browser_interact','Interact with a public web page using guarded Playwright actions; returns verification for each action.','CONTROL_COMPUTER',Risk.HIGH,{'type':'object','properties':{'url':{'type':'string'},'actions':{'type':'array','maxItems':25,'items':{'type':'object'}},'wait_ms':{'type':'integer','minimum':50,'maximum':5000}},'required':['url','actions']},browser_interact,True))
    router=getattr(app,'router',None)
    if router is not None:
        router.routes=[r for r in router.routes if getattr(r,'path',None)!='/api/browser/interact']
    post_route=getattr(app,'post',None)
    if post_route is None:return
    @post_route('/api/browser/interact')
    async def browser_interact_route(payload:dict,_:None=Depends(require_auth)):
        url=str(payload.get('url','')).strip();actions=payload.get('actions') or []
        if not url or not isinstance(actions,list):raise HTTPException(400,'url and actions are required')
        return await agent.run_tool('browser_interact',{'url':url,'actions':actions,'wait_ms':payload.get('wait_ms',300)})
