from __future__ import annotations
import asyncio,base64,ipaddress,json,socket,time,urllib.parse
from http.cookies import SimpleCookie
from fastapi import WebSocket,WebSocketDisconnect


def _validate_stream_endpoint(url):
    parsed=urllib.parse.urlsplit(str(url).strip())
    if parsed.scheme not in {'wss','ws'} or not parsed.hostname or parsed.username or parsed.password:raise ValueError('streaming STT endpoint must use ws/wss without credentials')
    if parsed.query or parsed.fragment:raise ValueError('streaming STT endpoint must not contain query or fragment')
    infos=socket.getaddrinfo(parsed.hostname,parsed.port or (443 if parsed.scheme=='wss' else 80),type=socket.SOCK_STREAM);ips={ipaddress.ip_address(info[4][0]) for info in infos}
    if parsed.scheme=='ws' and not all(ip.is_loopback for ip in ips):raise ValueError('ws streaming endpoints are restricted to loopback addresses')
    if parsed.scheme=='wss' and any(ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved for ip in ips):raise ValueError('streaming STT endpoint resolved to a non-public address')
    return parsed

async def _relay_stream(sock,settings):
    try:
        import websockets
    except Exception:
        await sock.send_json({'type':'error','error':'websockets client dependency is required'});return
    if not settings.stt_stream_url:
        await sock.send_json({'type':'mode','mode':'buffered'});return
    try:_validate_stream_endpoint(settings.stt_stream_url)
    except ValueError as exc:await sock.send_json({'type':'error','error':str(exc)});return
    headers={}
    if settings.stt_api_key:headers['Authorization']='Bearer '+settings.stt_api_key
    try:
        async with websockets.connect(settings.stt_stream_url,additional_headers=headers,max_size=32*1024*1024,proxy=None) as upstream:
            await upstream.send(json.dumps({'type':'start','model':settings.stt_model,'language':settings.stt_language}))
            async def producer():
                while True:
                    msg=await sock.receive()
                    if msg.get('bytes') is not None:await upstream.send(msg['bytes'])
                    elif msg.get('text'):
                        ctl=json.loads(msg['text']);await upstream.send(json.dumps(ctl))
                        if ctl.get('type')=='end':return
            async def consumer():
                async for msg in upstream:
                    if isinstance(msg,bytes):await sock.send_bytes(msg)
                    else:
                        try:data=json.loads(msg)
                        except json.JSONDecodeError:data={'type':'transcript','text':str(msg)}
                        await sock.send_json(data)
            await asyncio.gather(producer(),consumer())
    except WebSocketDisconnect:raise
    except Exception as e:await sock.send_json({'type':'error','error':f'streaming STT failed: {e}'})

def _ws_authenticated(sock,settings):
    auth_header=sock.headers.get('authorization','')
    token=auth_header[7:] if auth_header.startswith('Bearer ') else ''
    if settings.auth_mode=='api_key':
        return bool(settings.api_key and token and __import__('secrets').compare_digest(token,settings.api_key)) or not settings.api_key
    if settings.auth_mode=='oidc':
        raw=sock.headers.get('cookie','')
        try:
            c=SimpleCookie();c.load(raw);session=c.get('notsip_session')
            if session:
                auth=__import__('notsip.app',fromlist=['auth']).auth
                return bool(auth.validate_session(session.value))
        except Exception:
            return False
    return False

def attach(app,media,settings,auth_token=''):
    @app.websocket('/ws/voice')
    async def voice(sock:WebSocket):
        if not settings.voice_enabled:
            await sock.close(code=4403);return
        if not _ws_authenticated(sock,settings):await sock.close(code=4401);return
        await sock.accept()
        if settings.stt_stream_url:
            await _relay_stream(sock,settings);return
        chunks=[];mime='audio/webm';started=time.time()
        try:
            while True:
                message=await sock.receive()
                if message.get('bytes') is not None:
                    chunks.append(message['bytes'])
                    if sum(len(x) for x in chunks)>30*1024*1024:await sock.send_json({'type':'error','error':'audio stream exceeded 30MB'});chunks=[]
                    continue
                text=message.get('text') or ''
                if not text:continue
                try:control=json.loads(text)
                except json.JSONDecodeError:await sock.send_json({'type':'error','error':'invalid control JSON'});continue
                if control.get('type')=='start':
                    mime=str(control.get('mime','audio/webm'));chunks=[];started=time.time();await sock.send_json({'type':'ready','mode':'buffered'})
                elif control.get('type')=='end':
                    if not chunks:await sock.send_json({'type':'error','error':'no audio received'});continue
                    result=await media.transcribe(b''.join(chunks),mime,control.get('language',settings.stt_language));await sock.send_json({'type':'transcript','text':result['text'],'elapsed':time.time()-started});chunks=[]
        except WebSocketDisconnect:raise

    @app.websocket('/ws/perception')
    async def perception(sock:WebSocket):
        if not settings.vision_enabled:await sock.close(code=4403);return
        if not _ws_authenticated(sock,settings):await sock.close(code=4401);return
        await sock.accept()
        try:
            while True:
                try:payload=json.loads(await sock.receive_text());raw=base64.b64decode(payload['image_base64'],validate=True)
                except (json.JSONDecodeError,KeyError):await sock.send_json({'type':'error','error':'invalid perception payload'});continue
                if len(raw)>10*1024*1024:await sock.send_json({'type':'error','error':'image exceeds 10MB'});continue
                result=await media.perceive(raw,payload.get('prompt','Describe only observable evidence.'),payload.get('mime','image/jpeg'));await sock.send_json(result)
        except WebSocketDisconnect:raise
