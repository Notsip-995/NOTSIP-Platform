from __future__ import annotations
import asyncio
from .actor_context import set_actor,reset_actor

async def _voice_worker(events,agent,native_voice):
    q=events.subscribe()
    try:
        while True:
            event=await q.get()
            if event.type!='voice.transcript':continue
            text=str(event.payload.get('text','')).strip()
            if not text:continue
            verified=bool(event.payload.get('speaker_verified',False))
            actor='primary-user' if verified else 'voice:unverified'
            token=set_actor(actor)
            try:
                result=await agent.handle(text)
                response={'text':text,'verified_speaker':verified,'actor':actor,'result':result}
                if native_voice is not None and getattr(native_voice,'running',False):
                    spoken=str((result or {}).get('message') or (result or {}).get('response') or (result or {}).get('text') or '').strip() if isinstance(result,dict) else str(result or '').strip()
                    if spoken:response['playback']=await native_voice.speak_response(spoken)
                await events.publish(__import__('notsip.events',fromlist=['Event']).Event('voice.response',response,'voice-bridge'))
            except Exception as exc:
                await events.publish(__import__('notsip.events',fromlist=['Event']).Event('voice.agent_error',{'text':text,'error':str(exc),'actor':actor,'verified_speaker':verified},'voice-bridge'))
            finally:reset_actor(token)
    finally:events.unsubscribe(q)

def attach(app,events,agent,native_voice=None):
    @app.on_event('startup')
    async def start_voice_bridge():app.state.voice_bridge_task=asyncio.create_task(_voice_worker(events,agent,native_voice))
    @app.on_event('shutdown')
    async def stop_voice_bridge():
        task=getattr(app.state,'voice_bridge_task',None)
        if task:task.cancel()
