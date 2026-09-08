from __future__ import annotations
import time, uuid
from pathlib import Path
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


def _extension_for_mime(mime:str)->str:
    normalized=str(mime or '').split(';',1)[0].strip().lower()
    ext=_AUDIO_EXTENSIONS.get(normalized)
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


class MediaEngine:
    def __init__(self,settings,provider,data_dir:Path):
        self.settings=settings;self.provider=provider;self.root=Path(data_dir);self.audio=self.root/'audio';self.frames=self.root/'perception';self.audio.mkdir(parents=True,exist_ok=True);self.frames.mkdir(parents=True,exist_ok=True)
    async def transcribe(self,blob:bytes,mime='audio/webm',language=''):
        if not self.settings.stt_base_url or not self.settings.stt_model:raise RuntimeError('STT provider not configured')
        ext=_extension_for_mime(mime);p=self.audio/f'{uuid.uuid4()}.{ext}';p.write_bytes(blob);headers={'Authorization':'Bearer '+self.settings.stt_api_key} if self.settings.stt_api_key else {};data={'model':self.settings.stt_model}
        if language:data['language']=language
        async with httpx.AsyncClient(timeout=120) as c:r=await c.post(self.settings.stt_base_url.rstrip('/')+'/audio/transcriptions',headers=headers,files={'file':(p.name,blob,mime)},data=data);r.raise_for_status();d=r.json()
        return {'status':'SUCCESS','text':d.get('text',''),'provider':self.settings.stt_model,'path':str(p.relative_to(self.audio)),'input_mime':mime,'input_format':ext}
    async def speak(self,text,voice=''):
        if not self.settings.tts_base_url or not self.settings.tts_model:raise RuntimeError('TTS provider not configured')
        fmt=str(getattr(self.settings,'tts_format','mp3') or 'mp3').split(';',1)[0].strip().lower();fmt='wav' if getattr(self.settings,'native_voice_enabled',False) else fmt
        if fmt not in {'wav','mp3','ogg','m4a','webm'}:raise ValueError(f'unsupported TTS output format: {fmt}')
        headers={'Content-Type':'application/json'}
        if self.settings.tts_api_key:headers['Authorization']='Bearer '+self.settings.tts_api_key
        body={'model':self.settings.tts_model,'input':text,'voice':voice or self.settings.tts_voice,'response_format':fmt}
        async with httpx.AsyncClient(timeout=120) as c:r=await c.post(self.settings.tts_base_url.rstrip('/')+'/audio/speech',headers=headers,json=body);r.raise_for_status();audio=r.content
        if not _looks_like_audio(audio,fmt):raise RuntimeError(f'TTS provider returned bytes that do not match requested {fmt} format')
        p=self.audio/f'{uuid.uuid4()}.{fmt}';p.write_bytes(audio);return {'status':'SUCCESS','path':str(p.relative_to(self.audio)),'mime':'audio/'+fmt,'format':fmt,'bytes':len(audio)}
    async def perceive(self,frame:bytes,prompt='Describe the visible scene and note only evidence that is actually visible.',mime='image/jpeg'):
        if not self.settings.vision_enabled:raise RuntimeError('vision disabled')
        p=self.frames/f'{uuid.uuid4()}.jpg';p.write_bytes(frame);result=await self.provider.vision(prompt,frame,mime);msg=result.get('choices',[{}])[0].get('message',{}).get('content','');return {'status':'SUCCESS','observation':msg,'frame':str(p.relative_to(self.root)),'timestamp':time.time()}
