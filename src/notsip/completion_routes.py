from __future__ import annotations
import base64,binascii
from fastapi import Depends,File,Header,HTTPException,Request,UploadFile
from .events import Event
from .oauth_services import OAuthService
from .policy import Risk
from .tools import Tool
from .actor_context import current_actor

def attach(app, *, require_auth, media, maintenance, store, nodes, oauth, settings, events=None, registry=None, agent=None):
    async def require_user_or_device(request:Request):
        try:
            await require_auth(request);return {'kind':'user'}
        except HTTPException as user_error:
            device_id=request.headers.get('X-NOTSIP-Device-ID','').strip();token=request.headers.get('X-NOTSIP-Device-Token','').strip()
            if device_id and token and store.device_token_valid(device_id,token):return {'kind':'device','device_id':device_id}
            raise user_error

    def require_agent():
        if agent is None:raise HTTPException(503,'authorized agent is not available for mutation')
        return agent

    @app.post('/api/voice/transcribe')
    async def voice_transcribe(file:UploadFile=File(...),language:str='',_:dict=Depends(require_user_or_device)):
        if not settings.voice_enabled:raise HTTPException(503,'voice is disabled')
        if not settings.stt_base_url or not settings.stt_model:raise HTTPException(503,'STT is not configured')
        raw=await file.read()
        if len(raw)>30*1024*1024:raise HTTPException(413,'audio file too large')
        return await media.transcribe(raw,file.content_type or 'audio/webm',language or settings.stt_language)

    @app.post('/api/voice/speak')
    async def voice_speak(payload:dict,_:dict=Depends(require_user_or_device)):
        if not settings.voice_enabled:raise HTTPException(503,'voice is disabled')
        text=str(payload.get('text','')).strip()
        if not text:raise HTTPException(400,'text is required')
        if not settings.tts_base_url or not settings.tts_model:raise HTTPException(503,'TTS is not configured')
        return await media.speak(text,str(payload.get('voice') or settings.tts_voice))

    @app.post('/api/perception/frame')
    async def perception_frame(payload:dict,_:dict=Depends(require_user_or_device)):
        try:raw=base64.b64decode(str(payload.get('image_base64','')),validate=True)
        except (binascii.Error,ValueError):raise HTTPException(400,'invalid image_base64')
        if len(raw)>10*1024*1024:raise HTTPException(413,'image too large')
        if not settings.vision_enabled:raise HTTPException(503,'vision is disabled')
        result=await media.perceive(raw,str(payload.get('prompt') or 'Describe observable evidence only.'),str(payload.get('mime') or 'image/jpeg'));await store_fact_if_present(store,result,payload);return result

    @app.get('/api/self/inspect')
    async def self_inspect(_:None=Depends(require_auth)):return {'status':'SUCCESS','repository':str(maintenance.root),'files':maintenance.inventory()}
    @app.get('/api/self/read')
    async def self_read(path:str,_:None=Depends(require_auth)):
        try:return {'status':'SUCCESS','path':path,'content':maintenance.read(path)}
        except Exception as exc:raise HTTPException(400,str(exc))
    @app.get('/api/self/verify')
    async def self_verify(_:None=Depends(require_auth)):return maintenance.verify()
    @app.get('/api/federation/nodes')
    async def federation_nodes(_:None=Depends(require_auth)):return {'nodes':nodes.reconcile()}
    @app.get('/api/integrations/{provider_name}/calendar')
    async def integration_calendar(provider_name:str,account_id:str='',_:None=Depends(require_auth)):
        if provider_name not in oauth.PROFILES:raise HTTPException(400,'unsupported OAuth provider')
        try:return await oauth.calendar(provider_name,account_id or None)
        except Exception as exc:raise HTTPException(503,str(exc))
    @app.get('/api/integrations/{provider_name}/mail')
    async def integration_mail(provider_name:str,account_id:str='',_:None=Depends(require_auth)):
        if provider_name not in oauth.PROFILES:raise HTTPException(400,'unsupported OAuth provider')
        try:return await oauth.mail(provider_name,account_id or None)
        except Exception as exc:raise HTTPException(503,str(exc))
    def provider_guard(provider):
        if provider not in oauth.PROFILES:raise HTTPException(400,'unsupported OAuth provider')
        if provider not in {'google','microsoft'}:raise HTTPException(400,'provider does not support this operation')
    @app.post('/api/integrations/{provider_name}/calendar/events')
    async def integration_calendar_create(provider_name:str,payload:dict,_:None=Depends(require_auth)):
        provider_guard(provider_name);a=require_agent()
        return await a.run_tool('oauth_calendar_create',{'provider':provider_name,'account_id':str(payload.get('account_id','')) or None,'title':str(payload.get('title','')).strip(),'start':str(payload.get('start','')),'end':str(payload.get('end','')),'description':str(payload.get('description','')),'location':str(payload.get('location','')),'timezone':str(payload.get('timezone','UTC'))})
    @app.patch('/api/integrations/{provider_name}/calendar/events/{event_id}')
    async def integration_calendar_update(provider_name:str,event_id:str,payload:dict,_:None=Depends(require_auth)):
        provider_guard(provider_name);a=require_agent();changes=dict(payload);account_id=str(changes.pop('account_id','')) or None
        return await a.run_tool('oauth_calendar_update',{'provider':provider_name,'account_id':account_id,'event_id':event_id,'changes':changes})
    @app.delete('/api/integrations/{provider_name}/calendar/events/{event_id}')
    async def integration_calendar_delete(provider_name:str,event_id:str,account_id:str='',_:None=Depends(require_auth)):
        provider_guard(provider_name);a=require_agent();return await a.run_tool('oauth_calendar_delete',{'provider':provider_name,'account_id':account_id or None,'event_id':event_id})
    @app.post('/api/integrations/{provider_name}/mail/send')
    async def integration_mail_send(provider_name:str,payload:dict,_:None=Depends(require_auth)):
        provider_guard(provider_name);a=require_agent()
        return await a.run_tool('oauth_mail_send',{'provider':provider_name,'account_id':str(payload.get('account_id','')) or None,'to':str(payload.get('to','')),'subject':str(payload.get('subject','')),'body':str(payload.get('body',''))})
    @app.post('/api/events/signed')
    async def signed_event(payload:dict,signature:str='',x_notsip_event_signature:str=Header('',alias='X-NOTSIP-Event-Signature'),_:None=Depends(require_auth)):
        import hashlib,hmac,json
        if not settings.event_hmac_secret:raise HTTPException(503,'event HMAC secret is not configured')
        supplied=x_notsip_event_signature or signature
        raw=json.dumps(payload,separators=(',',':'),sort_keys=True).encode();expected=hmac.new(settings.event_hmac_secret.encode(),raw,hashlib.sha256).hexdigest()
        if not supplied or not hmac.compare_digest(expected,supplied):raise HTTPException(401,'invalid event signature')
        event=Event(payload.get('type','signed.external'),payload,'signed-external')
        if events is not None:await events.publish(event)
        return {'status':'ACCEPTED','event':payload,'published':events is not None}
    if registry is not None:
        registry.add(Tool('oauth_calendar_create','Create an event in an authorized Google or Microsoft calendar.','WRITE_CALENDAR',Risk.MEDIUM,{'type':'object','properties':{'provider':{'type':'string'},'account_id':{'type':'string'},'title':{'type':'string'},'start':{'type':'string'},'end':{'type':'string'},'description':{'type':'string'},'location':{'type':'string'},'timezone':{'type':'string'}},'required':['provider','title','start','end']},oauth.calendar_create))
        registry.add(Tool('oauth_calendar_update','Update an authorized Google or Microsoft calendar event.','WRITE_CALENDAR',Risk.MEDIUM,{'type':'object','properties':{'provider':{'type':'string'},'account_id':{'type':'string'},'event_id':{'type':'string'},'changes':{'type':'object'}},'required':['provider','event_id','changes']},oauth.calendar_update))
        registry.add(Tool('oauth_calendar_delete','Delete an authorized Google or Microsoft calendar event.','WRITE_CALENDAR',Risk.HIGH,{'type':'object','properties':{'provider':{'type':'string'},'account_id':{'type':'string'},'event_id':{'type':'string'}},'required':['provider','event_id']},oauth.calendar_delete,True))
        registry.add(Tool('oauth_mail_send','Send mail through an authorized Google or Microsoft account. Provider response is reported without claiming delivery.','SEND_EMAIL',Risk.HIGH,{'type':'object','properties':{'provider':{'type':'string'},'account_id':{'type':'string'},'to':{'type':'string'},'subject':{'type':'string'},'body':{'type':'string'}},'required':['provider','to','subject','body']},oauth.send_mail,True))

def store_fact_if_present(store,result,payload):
    observation=result.get('observation') if isinstance(result,dict) else None
    if observation:
        store.fact(observation,'vision','',0.65,{'prompt':payload.get('prompt',''),'actor':current_actor()})
