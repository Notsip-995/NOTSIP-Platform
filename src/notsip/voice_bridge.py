from __future__ import annotations
import asyncio

def attach(app, events, agent, native_voice=None):
    async def worker():
        q=events.subscribe()
        try:
            while True:
                event=await q.get()
                if event.type!='voice.transcript':continue
                text=str(event.payload.get('text','')).strip()
                if not text:continue
                try:
                    result=await agent.handle(text)
                    response={'text':text,'result':result}
                    if native_voice is not None and getattr(native_voice,'running',False):
                        spoken=str((result or {}).get('message') or (result or {}).get('response') or (result or {}).get('text') or '').strip() if isinstance(result,dict) else str(result or '').strip()
                        if spoken:response['playback']=await native_voice.speak_response(spoken)
                    await events.publish(__import__('notsip.events',fromlist=['Event']).Event('voice.response',response,'voice-bridge'))
                except Exception as exc:
                    await events.publish(__import__('notsip.events',fromlist=['Event']).Event('voice.agent_error',{'text':text,'error':str(exc)},'voice-bridge'))
        finally:
            events.unsubscribe(q)
    @app.on_event('startup')
    async def start_voice_bridge():app.state.voice_bridge_task=asyncio.create_task(worker())
    @app.on_event('shutdown')
    async def stop_voice_bridge():
        task=getattr(app.state,'voice_bridge_task',None)
        if task:task.cancel()
