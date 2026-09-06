from fastapi import Depends, HTTPException

def attach(app,require_auth,web,emailc):
    @app.get('/api/search')
    async def search(q:str,count:int=5,_:None=Depends(require_auth)):
        if not web.enabled:raise HTTPException(503,'Web search not configured')
        return {'results':await web.search(q,max(1,min(int(count),20)))}
    @app.get('/api/email/status')
    async def email_status(_:None=Depends(require_auth)):
        return {'configured':emailc.enabled,'smtp':bool(emailc.smtp_host),'imap':bool(emailc.imap_host),'username_configured':bool(emailc.username)}
