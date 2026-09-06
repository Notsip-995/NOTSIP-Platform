from __future__ import annotations
import asyncio, base64, json, time
from fastapi import WebSocket, WebSocketDisconnect

def attach(app,media,settings,auth_token=''):
    @app.websocket('/ws/voice')
    async def voice(sock:WebSocket):
        if auth_token and sock.headers.get('authorization')!='Bearer '+auth_token:
            await sock.close(code=4401); return
        await sock.accept(); chunks=[]; mime='audio/webm'; started=time.time()
        try:
            while True:
                message=await sock.receive()
                if message.get('bytes') is not None:
                    chunks.append(message['bytes'])
                    if sum(len(x) for x in chunks)>30*1024*1024:
                        await sock.send_json({'type':'error','error':'audio stream exceeded 30MB'});chunks=[]
                    continue
                text=message.get('text') or ''
                if not text: continue
                control=json.loads(text)
                if control.get('type')=='start':
                    chunks=[];mime=control.get('mime','audio/webm');started=time.time();await sock.send_json({'type':'ready'})
                elif control.get('type')=='end':
                    if not chunks: await sock.send_json({'type':'error','error':'no audio received'});continue
                    result=await media.transcribe(b''.join(chunks),mime,control.get('language',settings.stt_language));await sock.send_json({'type':'transcript','text':result['text'],'elapsed':time.time()-started});chunks=[]
        except WebSocketDisconnect: pass

    @app.websocket('/ws/perception')
    async def perception(sock:WebSocket):
        if auth_token and sock.headers.get('authorization')!='Bearer '+auth_token:
            await sock.close(code=4401); return
        await sock.accept()
        try:
            while True:
                payload=json.loads(await sock.receive_text())
                raw=base64.b64decode(payload['image_base64'],validate=True)
                if len(raw)>10*1024*1024: await sock.send_json({'type':'error','error':'image exceeds 10MB'});continue
                result=await media.perceive(raw,payload.get('prompt','Describe only observable evidence.'),payload.get('mime','image/jpeg'));await sock.send_json(result)
        except WebSocketDisconnect: pass
