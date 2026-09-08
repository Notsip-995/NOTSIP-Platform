from __future__ import annotations
import urllib.parse
import httpx

class SpeakerIdentityUnavailable(RuntimeError):
    pass

class SpeakerIdentityAdapter:
    """Optional external speaker-verification provider. No provider means no identity claim."""
    def __init__(self,base_url='',token=''):
        self.base_url=str(base_url or '').strip().rstrip('/');self.token=str(token or '')
    @property
    def configured(self):return bool(self.base_url)
    async def verify(self,audio:bytes,mime='audio/webm'):
        if not self.configured:raise SpeakerIdentityUnavailable('speaker identity provider is not configured')
        parsed=urllib.parse.urlparse(self.base_url)
        if parsed.scheme!='https' or not parsed.hostname:raise ValueError('speaker identity provider must use HTTPS')
        headers={'Authorization':'Bearer '+self.token} if self.token else {}
        files={'audio':('voice.webm',audio,mime)}
        async with httpx.AsyncClient(timeout=30) as client:
            response=await client.post(self.base_url+'/verify',files=files,headers=headers);response.raise_for_status();data=response.json()
        verified=bool(data.get('verified',False));speaker_id=str(data.get('speaker_id','')).strip();confidence=float(data.get('confidence',0) or 0)
        if verified and not speaker_id:raise ValueError('speaker provider claimed verification without a speaker_id')
        return {'status':'SUCCESS' if verified else 'FAILURE','verified':verified,'speaker_id':speaker_id if verified else '','confidence':max(0.0,min(1.0,confidence)),'provider':self.base_url}
