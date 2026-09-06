from __future__ import annotations
import base64, ctypes, hashlib, json, os, secrets, subprocess, time
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class SecretStore:
    """Windows-DPAPI-backed local secret store with an encrypted-file fallback."""
    def __init__(self, root: Path):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True); self.path=self.root/'secrets.enc'; self._key=self._load_or_create_key()
    def _dpapi(self, data: bytes, decrypt=False):
        if os.name!='nt': return None
        try:
            class BLOB(ctypes.Structure):
                _fields_=[('cbData',ctypes.c_uint32),('pbData',ctypes.POINTER(ctypes.c_byte))]
            crypt32=ctypes.windll.crypt32; kernel32=ctypes.windll.kernel32
            if decrypt:
                raw=ctypes.create_string_buffer(data); inp=BLOB(len(data),ctypes.cast(raw,ctypes.POINTER(ctypes.c_byte))); out=BLOB()
                if not crypt32.CryptUnprotectData(ctypes.byref(inp),None,None,None,None,0,ctypes.byref(out)): return None
                try:return ctypes.string_at(out.pbData,out.cbData)
                finally: kernel32.LocalFree(out.pbData)
            raw=ctypes.create_string_buffer(data); inp=BLOB(len(data),ctypes.cast(raw,ctypes.POINTER(ctypes.c_byte))); out=BLOB()
            if not crypt32.CryptProtectData(ctypes.byref(inp),None,None,None,None,0,ctypes.byref(out)): return None
            try:return ctypes.string_at(out.pbData,out.cbData)
            finally: kernel32.LocalFree(out.pbData)
        except Exception:return None
    def _load_or_create_key(self):
        env=os.getenv('NOTSIP_MASTER_KEY','')
        if env:
            return hashlib.sha256(env.encode()).digest()
        p=self.root/'master.key'
        if p.exists():
            raw=p.read_bytes(); dec=self._dpapi(raw,True)
            if dec: return dec[:32]
            return hashlib.sha256(raw).digest()
        key=secrets.token_bytes(32); enc=self._dpapi(key,False) or key; p.write_bytes(enc)
        try: p.chmod(0o600)
        except Exception: pass
        return key
    def load(self):
        if not self.path.exists(): return {}
        blob=json.loads(self.path.read_text(encoding='utf-8')); nonce=base64.b64decode(blob['nonce']); ct=base64.b64decode(blob['data']); return json.loads(AESGCM(self._key).decrypt(nonce,ct,None))
    def save(self,data):
        nonce=secrets.token_bytes(12); ct=AESGCM(self._key).encrypt(nonce,json.dumps(data,sort_keys=True).encode(),None); tmp=self.path.with_suffix('.tmp'); tmp.write_text(json.dumps({'nonce':base64.b64encode(nonce).decode(),'data':base64.b64encode(ct).decode()}),encoding='utf-8'); os.replace(tmp,self.path)
        try:self.path.chmod(0o600)
        except Exception:pass
    def get(self,name,default=None): return self.load().get(name,default)
    def set(self,name,value): d=self.load(); d[name]=value; self.save(d)

class OIDCProvider:
    def __init__(self,issuer,client_id,client_secret='',redirect_uri='',scopes='openid profile email'):
        self.issuer=(issuer or '').rstrip('/'); self.client_id=client_id; self.client_secret=client_secret; self.redirect_uri=redirect_uri; self.scopes=scopes; self.metadata={}
    @property
    def configured(self): return bool(self.issuer and self.client_id and self.redirect_uri)
    async def discover(self):
        if not self.configured: raise RuntimeError('OIDC not configured')
        import httpx
        async with httpx.AsyncClient(timeout=20) as c:
            r=await c.get(self.issuer+'/.well-known/openid-configuration'); r.raise_for_status(); self.metadata=r.json(); return self.metadata
    async def authorize_url(self,state,challenge):
        m=self.metadata or await self.discover(); from urllib.parse import urlencode
        return m['authorization_endpoint']+'?'+urlencode({'client_id':self.client_id,'redirect_uri':self.redirect_uri,'response_type':'code','scope':self.scopes,'state':state,'code_challenge':challenge,'code_challenge_method':'S256'})
    async def exchange(self,code,verifier):
        m=self.metadata or await self.discover(); import httpx
        data={'grant_type':'authorization_code','code':code,'client_id':self.client_id,'redirect_uri':self.redirect_uri,'code_verifier':verifier}
        if self.client_secret:data['client_secret']=self.client_secret
        async with httpx.AsyncClient(timeout=20) as c:
            r=await c.post(m['token_endpoint'],data=data); r.raise_for_status(); return r.json()
    async def userinfo(self,access_token):
        m=self.metadata or await self.discover(); url=m.get('userinfo_endpoint')
        if not url:return {}
        import httpx
        async with httpx.AsyncClient(timeout=20) as c:
            r=await c.get(url,headers={'Authorization':'Bearer '+access_token}); r.raise_for_status(); return r.json()

def pkce_pair():
    verifier=secrets.token_urlsafe(64); challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode(); return verifier,challenge

class AuthManager:
    def __init__(self, settings, root: Path):
        self.settings=settings; self.secrets=SecretStore(root); self.sessions={}; self.oidc=OIDCProvider(settings.oidc_issuer,settings.oidc_client_id,settings.oidc_client_secret,settings.oidc_redirect_uri,settings.oidc_scopes)
    @property
    def mode(self): return self.settings.auth_mode
    @property
    def api_key_enabled(self): return bool(self.settings.api_key)
    def mint_session(self,claims):
        token=secrets.token_urlsafe(48); self.sessions[token]={'claims':claims,'expires':time.time()+self.settings.session_ttl}; return token
    def validate_session(self,token):
        s=self.sessions.get(token); return bool(s and s['expires']>time.time())
