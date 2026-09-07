from __future__ import annotations
import asyncio, io, math, platform, threading, time, wave

class NativeVoiceWorker:
    def __init__(self,settings,media,events):
        self.settings=settings;self.media=media;self.events=events;self.running=False;self.thread=None;self.loop=None;self._playback_lock=threading.Lock();self._playback_stop=threading.Event()
    def start(self):
        if self.running:return {'status':'ALREADY_RUNNING'}
        if platform.system()!='Windows':return {'status':'UNAVAILABLE','reason':'Windows required'}
        try:import sounddevice as sd
        except Exception as e:return {'status':'UNAVAILABLE','reason':f'sounddevice unavailable: {e}'}
        self.running=True;self.loop=asyncio.get_running_loop();self.thread=threading.Thread(target=self._capture,args=(sd,),daemon=True);self.thread.start();return {'status':'STARTED'}
    def stop(self):
        self.running=False;self._playback_stop.set();return {'status':'STOPPING'}
    def interrupt(self):
        self._playback_stop.set();return {'status':'INTERRUPTED'}
    def _capture(self,sd):
        rate=int(getattr(self.settings,'voice_sample_rate',16000));block=int(rate*.2);threshold=float(getattr(self.settings,'vad_rms_threshold',700));silence_blocks=int(getattr(self.settings,'vad_silence_blocks',8));pre=[];frames=[];silent=0;active=False
        def cb(indata,frames_count,time_info,status):
            nonlocal active,silent,frames,pre
            raw=bytes(indata);pre.append(raw);pre=pre[-3:]
            if len(raw)<2:return
            vals=[int.from_bytes(raw[i:i+2],'little',signed=True) for i in range(0,len(raw)-1,2)]
            rms=math.sqrt(sum(v*v for v in vals)/max(1,len(vals)))
            if rms>=threshold:
                if not active:frames=list(pre);active=True
                frames.append(raw);silent=0;self._playback_stop.set()
            elif active:
                frames.append(raw);silent+=1
                if silent>=silence_blocks:
                    blob=b''.join(frames);frames=[];silent=0;active=False
                    if self.loop:asyncio.run_coroutine_threadsafe(self._utterance(blob,rate),self.loop)
        try:
            with sd.RawInputStream(samplerate=rate,channels=1,dtype='int16',blocksize=block,callback=cb):
                while self.running:time.sleep(.2)
        except Exception as e:
            if self.loop:asyncio.run_coroutine_threadsafe(self._emit('native_voice.error',{'error':str(e)}),self.loop)
    @staticmethod
    def _wav(pcm:bytes,rate:int)->bytes:
        out=io.BytesIO()
        with wave.open(out,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(pcm)
        return out.getvalue()
    async def _utterance(self,pcm,rate):
        try:
            blob=self._wav(pcm,rate);result=await self.media.transcribe(blob,'audio/wav',getattr(self.settings,'stt_language',''));text=result.get('text','').strip();wake=getattr(self.settings,'wake_word','').strip().lower()
            if wake and not text.lower().startswith(wake):return
            await self._emit('voice.transcript',{'text':text,'wake_word':wake})
        except Exception as e:await self._emit('native_voice.error',{'error':str(e)})
    async def speak_response(self,text):
        if not self.running or not getattr(self.settings,'native_voice_enabled',False):return {'status':'DISABLED'}
        if (getattr(self.settings,'tts_format','') or '').lower()!='wav':return {'status':'UNAVAILABLE','reason':'native playback requires TTS format WAV'}
        try:
            result=await self.media.speak(text,getattr(self.settings,'tts_voice',''));path=self.media.audio/result['path'];return await asyncio.to_thread(self._play_wav,path)
        except Exception as exc:
            await self._emit('native_voice.error',{'error':f'TTS playback failed: {exc}'});return {'status':'FAILURE','error':str(exc)}
    def _play_wav(self,path):
        try:import sounddevice as sd
        except Exception as e:return {'status':'UNAVAILABLE','reason':f'sounddevice unavailable: {e}'}
        with wave.open(str(path),'rb') as w:channels=w.getnchannels();rate=w.getframerate();width=w.getsampwidth();frames=w.readframes(w.getnframes())
        if width!=2:return {'status':'UNAVAILABLE','reason':'only 16-bit WAV playback is supported'}
        import array
        samples=array.array('h');samples.frombytes(frames)
        if __import__('sys').byteorder!='little':samples.byteswap()
        self._playback_stop.clear()
        with self._playback_lock:
            try:
                sd.play(samples,rate,channels=channels);start=time.time()
                while self.running and not self._playback_stop.is_set() and time.time()-start<max(5,len(samples)/(rate*max(1,channels))+5):time.sleep(.05)
                if self._playback_stop.is_set():sd.stop();return {'status':'INTERRUPTED'}
                sd.wait();return {'status':'PLAYED','path':str(path)}
            finally:
                try:sd.stop()
                except Exception:pass
    async def _emit(self,typ,payload):
        from .events import Event
        await self.events.publish(Event(typ,payload,'native-voice'))
