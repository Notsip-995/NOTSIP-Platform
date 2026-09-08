from __future__ import annotations
from fastapi import Depends,HTTPException
from .actor_context import current_actor
from .conversations import ConversationStore


def attach(app,require_auth,agent,root):
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None) not in {'/api/sessions','/api/sessions/{session_id}','/api/sessions/{session_id}/select'}]
    def store_for_actor():return ConversationStore(root,current_actor())
    @app.get('/api/sessions')
    async def list_sessions(_:None=Depends(require_auth)):
        return {'sessions':store_for_actor().list()}
    @app.post('/api/sessions')
    async def create_session(payload:dict,_:None=Depends(require_auth)):
        s=store_for_actor().create(str(payload.get('title','New conversation')));agent.session=s;return s
    @app.get('/api/sessions/{session_id}')
    async def get_session(session_id:str,_:None=Depends(require_auth)):
        store=store_for_actor();session=next((x for x in store.list() if x.get('id')==session_id),None)
        if not session:raise HTTPException(404,'session not found')
        return {'session':session,'messages':store.history(session_id,200)}
    @app.post('/api/sessions/{session_id}/select')
    async def select_session(session_id:str,_:None=Depends(require_auth)):
        store=store_for_actor();session=next((x for x in store.list() if x.get('id')==session_id),None)
        if not session:raise HTTPException(404,'session not found')
        agent.session=session;return session
