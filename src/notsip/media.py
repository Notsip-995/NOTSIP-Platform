from __future__ import annotations
import time, uuid
from pathlib import Path
import httpx
class MediaEngine:
    def __init__(self,settings,provider,data_dir:Path):
        self.settings=settings;self.provider=provider;self.root=Path(data_dir);self.audio=self.root/'audio';self.frames=self.root/'perception';self.audio.mkdir(parents=True,exist_ok=True);self.frames.mkdir(parents=True,exist_ok=True)
    async def transcribe(self,blob:bytes,mime='audio/webm',language=''):
        if not self.settings.stt_base_url or not self.settings.stt_model:raise RuntimeError('STT provider not configured')
        ext='webm' if 'webm' in mime else 'wav';p=self.audio/f'{uuid.uuid4()}.{ext}';p.write_bytes(blob);headers={'Authorization':'Bearer '+self.settings.stt_api_key} if self.settings.stt_api_key else {};data={'model':self.settings.stt_model};
        if language:data['language']=language
        async with httpx.AsyncClient(timeout=120) as c:r=await c.post(self.settings.stt_base_url.rstrip('/')+'/audio/transcriptions',headers=headers,files={'file':(p.name,blob,mime)},data=data);r.raise_for_status();d=r.json()
        return {'status':'SUCCESS','text':d.get('text',''),'provider':self.settings.stt_model,'path':str(p.relative_to(self.audio))}
    async def speak(self,text,voice=''):
        if not self.settings.tts_base_url or not self.settings.tts_model:raise RuntimeError('TTS provider not configured')
        fmt='wav' if getattr(self.settings,'native_voice_enabled',False) else self.settings.tts_format
        headers={'Content-Type':'application/json'}
        if self.settings.tts_api_key:headers['Authorization']='Bearer '+self.settings.tts_api_key
        body={'model':self.settings.tts_model,'input':text,'voice':voice or self.settings.tts_voice,'response_format':fmt}
        async with httpx.AsyncClient(timeout=120) as c:r=await c.post(self.settings.tts_base_url.rstrip('/')+'/audio/speech',headers=headers,json=body);r.raise_for_status();audio=r.content
        p=self.audio/f'{uuid.uuid4()}.{fmt}';p.write_bytes(audio);return {'status':'SUCCESS','path':str(p.relative_to(self.audio)),'mime':'audio/'+fmt,'bytes':len(audio)}
    async def perceive(self,frame:bytes,prompt='Describe the visible scene and note only evidence that is actually visible.',mime='image/jpeg'):
        if not self.settings.vision_enabled:raise RuntimeError('vision disabled')
        p=self.frames/f'{uuid.uuid4()}.jpg';p.write_bytes(frame);result=await self.provider.vision(prompt,frame,mime);msg=result.get('choices',[{}])[0].get('message',{}).get('content','');return {'status':'SUCCESS','observation':msg,'frame':str(p.relative_to(self.root)),'timestamp':time.time()}