from __future__ import annotations
import asyncio,math,platform,queue,threading,time

class NativeVoiceWorker:
    def __init__(self,settings,media,events):
        self.settings=settings;self.media=media;self.events=events;self.running=False;self.thread=None;self.loop=None
    def start(self):
        if self.running:return {'status':'ALREADY_RUNNING'}
        if platform.system()!='Windows':return {'status':'UNAVAILABLE','reason':'Windows required'}
        try:import sounddevice as sd
        except Exception as e:return {'status':'UNAVAILABLE','reason':f'sounddevice unavailable: {e}'}
        self.running=True;self.loop=asyncio.get_running_loop();self.thread=threading.Thread(target=self._capture,args=(sd,),daemon=True);self.thread.start();return {'status':'STARTED'}
    def stop(self):self.running=False;return {'status':'STOPPING'}
    def _capture(self,sd):
        rate=int(getattr(self.settings,'voice_sample_rate',16000));block=int(rate*.2);threshold=float(getattr(self.settings,'vad_rms_threshold',700));silence_blocks=int(getattr(self.settings,'vad_silence_blocks',8));pre=[];frames=[];silent=0;active=False
        def cb(indata,frames_count,time_info,status):
            nonlocal active,silent,frames,pre
            raw=bytes(indata);pre.append(raw);pre=pre[-3:]
            if len(raw)<2:return
            vals=[]
            for i in range(0,len(raw)-1,2):vals.append(int.from_bytes(raw[i:i+2],'little',signed=True))
            rms=math.sqrt(sum(v*v for v in vals)/max(1,len(vals)))
            if rms>=threshold:
                if not active:frames=list(pre);active=True
                frames.append(raw);silent=0
            elif active:
                frames.append(raw);silent+=1
                if silent>=silence_blocks:
                    blob=b''.join(frames);frames=[];silent=0;active=False
                    if self.loop:asyncio.run_coroutine_threadsafe(self._utterance(blob),self.loop)
        try:
            with sd.RawInputStream(samplerate=rate,channels=1,dtype='int16',blocksize=block,callback=cb):
                while self.running:time.sleep(.2)
        except Exception as e:
            if self.loop:asyncio.run_coroutine_threadsafe(self._emit('native_voice.error',{'error':str(e)}),self.loop)
    async def _utterance(self,pcm):
        try:
            # Providers normally expect WAV/WebM. The generic HTTP STT adapter
            # accepts a byte payload; mark it as PCM so custom STT gateways can decode it.
            result=await self.media.transcribe(pcm,'audio/pcm',getattr(self.settings,'stt_language',''))
            text=result.get('text','').strip();wake=getattr(self.settings,'wake_word','').strip().lower()
            if wake and not text.lower().startswith(wake):return
            await self._emit('voice.transcript',{'text':text,'wake_word':wake})
        except Exception as e:await self._emit('native_voice.error',{'error':str(e)})
    async def _emit(self,typ,payload):
        from .events import Event
        await self.events.publish(Event(typ,payload,'native-voice'))
