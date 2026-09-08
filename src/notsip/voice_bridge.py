from __future__ import annotations
import asyncio
from .actor_context import set_actor,reset_actor
from .voice_identity import SpeakerIdentityAdapter,SpeakerIdentityUnavailable

async def _voice_worker(events,agent,native_voice,speaker_identity):
    q=events.subscribe()
    try:
        while True:
            event=await q.get()
            if event.type!='voice.transcript':continue
            payload=event.payload or {};text=str(payload.get('text','')).strip()
            if not text:continue
            verified=bool(payload.get('speaker_verified',False));speaker_id=str(payload.get('speaker_id','')).strip()
            if not verified and payload.get('audio_base64'):
                try:
                    import base64
                    check=await speaker_identity.verify(base64.b64decode(payload['audio_base64']),str(payload.get('mime','audio/webm')))
                    verified=bool(check.get('verified'));speaker_id=str(check.get('speaker_id','')).strip()
                except SpeakerIdentityUnavailable:
                    pass
                except Exception as exc:
                    await events.publish(__import__('notsip.events',fromlist=['Event']).Event('voice.identity_error',{'text':text,'error':str(exc)},'voice-bridge'));continue
            actor=speaker_id if verified and speaker_id else ('primary-user' if verified else 'voice:unverified')
            token=set_actor(actor)
            try:
                result=await agent.handle(text);response={'text':text,'verified_speaker':verified,'speaker_id':speaker_id,'actor':actor,'result':result}
                if native_voice is not None and getattr(native_voice,'running',False):
                    spoken=str((result or {}).get('message') or (result or {}).get('response') or (result or {}).get('text') or '').strip() if isinstance(result,dict) else str(result or '').strip()
                    if spoken:response['playback']=await native_voice.speak_response(spoken)
                await events.publish(__import__('notsip.events',fromlist=['Event']).Event('voice.response',response,'voice-bridge'))
            except Exception as exc:
                await events.publish(__import__('notsip.events',fromlist=['Event']).Event('voice.agent_error',{'text':text,'error':str(exc),'actor':actor,'verified_speaker':verified},'voice-bridge'))
            finally:reset_actor(token)
    finally:events.unsubscribe(q)

def attach(app,events,agent,native_voice=None,settings=None):
    settings=settings or getattr(agent,'settings',None)
    speaker_identity=SpeakerIdentityAdapter(getattr(settings,'speaker_identity_url',''),getattr(settings,'speaker_identity_token',''))
    @app.on_event('startup')
    async def start_voice_bridge():app.state.voice_bridge_task=asyncio.create_task(_voice_worker(events,agent,native_voice,speaker_identity))
    @app.on_event('shutdown')
    async def stop_voice_bridge():
        task=getattr(app.state,'voice_bridge_task',None)
        if task:task.cancel()
