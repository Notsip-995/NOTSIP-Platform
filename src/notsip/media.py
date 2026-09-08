from __future__ import annotations
import ipaddress,socket,time,uuid
from pathlib import Path
from urllib.parse import urlsplit
import httpx

_AUDIO_EXTENSIONS={
    'audio/webm':'webm',
    'audio/wav':'wav',
    'audio/x-wav':'wav',
    'audio/wave':'wav',
    'audio/mpeg':'mp3',
    'audio/mp3':'mp3',
    'audio/ogg':'ogg',
    'audio/opus':'ogg',
    'audio/mp4':'m4a',
    'audio/x-m4a':'m4a',
}
MAX_AUDIO_RESPONSE_BYTES=25*1024*1024

def _extension_for_mime(mime:str)->str:
    normalized=str(mime or '').split(';',1)[0].strip().lower();ext=_AUDIO_EXTENSIONS.get(normalized)
    if not ext:raise ValueError(f'unsupported audio MIME type: {mime or "missing"}')
    return ext

def _looks_like_audio(blob:bytes,fmt:str)->bool:
    if not blob:return False
    if fmt=='wav':return len(blob)>=12 and blob[:4]==b'RIFF' and blob[8:12]==b'WAVE'
    if fmt=='webm':return blob.startswith(b'\x1a\x45\xdf\xa3')
    if fmt=='ogg':return blob.startswith(b'OggS')
    if fmt=='m4a':return len(blob)>=12 and blob[4:8]==b'ftyp'
    if fmt=='mp3':return blob.startswith(b'ID3') or (len(blob)>=2 and blob[0]==0xff and blob[1]&0xe0==0xe0)
    return True

def _validate_endpoint(url):
    parsed=urlsplit(str(url).strip())
    if not parsed.hostname:raise ValueError('media provider endpoint must include a hostname')
    if parsed.username or parsed.password:raise ValueError('media provider endpoint must not contain credentials')
    if parsed.query or parsed.fragment:raise ValueError('media provider endpoint must not contain query or fragment')
    if parsed.scheme not in {'https','http'}:raise ValueError('media provider endpoint must use HTTP or HTTPS')
    infos=socket.getaddrinfo(parsed.hostname,parsed.port or (443 if parsed.scheme=='https' else 80),type=socket.SOCK_STREAM);ips={ipaddress.ip_address(info[4][0]) for info in infos}
    if parsed.scheme=='http' and not all(ip.is_loopback for ip in ips):raise ValueError('HTTP media provider endpoints are restricted to loopback addresses')
    if parsed.scheme=='https' and any(ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved for ip in ips):raise ValueError('media provider endpoint resolved to a non-public address')
    return parsed

class MediaEngine:
    def __init__(self,settings,provider,data_dir:Path):
        self.settings=settings;self.provider=provider;self.root=Path(data_dir);self.audio=self.root/'audio';self.frames=self.root/'perception';self.audio.mkdir(parents=True,exist_ok=True);self.frames.mkdir(parents=True,exist_ok=True)
    async def transcribe(self,blob:bytes,mime='audio/webm',language=''):
        if not self.settings.stt_base_url or not self.settings.stt_model:raise RuntimeError('STT provider not configured')
        _validate_endpoint(self.settings.stt_base_url)
        ext=_extension_for_mime(mime);p=self.audio/f'{uuid.uuid4()}.{ext}';p.write_bytes(blob);headers={'Authorization':'Bearer '+self.settings.stt_api_key} if self.settings.stt_api_key else {};data={'model':self.settings.stt_model}
        if language:data['language']=language
        async with httpx.AsyncClient(timeout=120,follow_redirects=False,trust_env=False) as c:
            r=await c.post(self.settings.stt_base_url.rstrip('/')+'/audio/transcriptions',headers=headers,files={'file':(p.name,blob,mime)},data=data)
            if r.is_redirect or r.is_permanent_redirect:raise RuntimeError('STT provider redirect rejected')
            r.raise_for_status();d=r.json()
        return {'status':'SUCCESS','text':d.get('text',''),'provider':self.settings.stt_model,'path':str(p.relative_to(self.audio)),'input_mime':mime,'input_format':ext}
    async def speak(self,text,voice=''):
        if not self.settings.tts_base_url or not self.settings.tts_model:raise RuntimeError('TTS provider not configured')
        _validate_endpoint(self.settings.tts_base_url)
        fmt=str(getattr(self.settings,'tts_format','mp3') or 'mp3').split(';',1)[0].strip().lower();fmt='wav' if getattr(self.settings,'native_voice_enabled',False) else fmt
        if fmt not in {'wav','mp3','ogg','m4a','webm'}:raise ValueError(f'unsupported TTS output format: {fmt}')
        headers={'Content-Type':'application/json'}
        if self.settings.tts_api_key:headers['Authorization']='Bearer '+self.settings.tts_api_key
        body={'model':self.settings.tts_model,'input':text,'voice':voice or self.settings.tts_voice,'response_format':fmt}
        async with httpx.AsyncClient(timeout=120,follow_redirects=False,trust_env=False) as c:
            r=await c.post(self.settings.tts_base_url.rstrip('/')+'/audio/speech',headers=headers,json=body)
            if r.is_redirect or r.is_permanent_redirect:raise RuntimeError('TTS provider redirect rejected')
            r.raise_for_status();audio=r.content
        if len(audio)>MAX_AUDIO_RESPONSE_BYTES:raise RuntimeError('TTS provider response exceeded safety limit')
        if not _looks_like_audio(audio,fmt):raise RuntimeError(f'TTS provider returned bytes that do not match requested {fmt} format')
        p=self.audio/f'{uuid.uuid4()}.{fmt}';p.write_bytes(audio);return {'status':'SUCCESS','path':str(p.relative_to(self.audio)),'mime':'audio/'+fmt,'format':fmt,'bytes':len(audio)}
    async def perceive(self,frame:bytes,prompt='Describe the visible scene and note only evidence that is actually visible.',mime='image/jpeg'):
        if not self.settings.vision_enabled:raise RuntimeError('vision disabled')
        p=self.frames/f'{uuid.uuid4()}.jpg';p.write_bytes(frame);result=await self.provider.vision(prompt,frame,mime);msg=result.get('choices',[{}])[0].get('message',{}).get('content','');return {'status':'SUCCESS','observation':msg,'frame':str(p.relative_to(self.root)),'timestamp':time.time()}
