from __future__ import annotations
import base64, ctypes, hashlib, json, os, secrets, time, threading
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class SecretStore:
    def __init__(self,root:Path):self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.path=self.root/'secrets.enc';self._lock=threading.RLock();self._key=self._load_or_create_key()
    def _dpapi(self,data,decrypt=False):
        if os.name!='nt':return None
        try:
            class BLOB(ctypes.Structure):_fields_=[('cbData',ctypes.c_uint32),('pbData',ctypes.POINTER(ctypes.c_byte))]
            crypt32=ctypes.windll.crypt32;kernel32=ctypes.windll.kernel32;raw=ctypes.create_string_buffer(data);inp=BLOB(len(data),ctypes.cast(raw,ctypes.POINTER(ctypes.c_byte)));out=BLOB();fn=crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
            if not fn(ctypes.byref(inp),None,None,None,None,0,ctypes.byref(out)):return None
            try:return ctypes.string_at(out.pbData,out.cbData)
            finally:kernel32.LocalFree(out.pbData)
        except Exception:return None
    def _load_or_create_key(self):
        env=os.getenv('NOTSIP_MASTER_KEY','')
        if env:return hashlib.sha256(env.encode()).digest()
        p=self.root/'master.key'
        if p.exists():
            raw=p.read_bytes();dec=self._dpapi(raw,True);return dec[:32] if dec else hashlib.sha256(raw).digest()
        key=secrets.token_bytes(32);p.write_bytes(self._dpapi(key) or key)
        try:p.chmod(0o600)
        except Exception:pass
        return key
    def load(self):
        with self._lock:
            if not self.path.exists():return {}
            b=json.loads(self.path.read_text(encoding='utf-8'));return json.loads(AESGCM(self._key).decrypt(base64.b64decode(b['nonce']),base64.b64decode(b['data']),None))
    def save(self,data):
        with self._lock:
            n=secrets.token_bytes(12);ct=AESGCM(self._key).encrypt(n,json.dumps(data,sort_keys=True).encode(),None);tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps({'nonce':base64.b64encode(n).decode(),'data':base64.b64encode(ct).decode()}),encoding='utf-8');os.replace(tmp,self.path)
            try:self.path.chmod(0o600)
            except Exception:pass
    def get(self,name,default=None):
        with self._lock:return self.load().get(name,default)
    def set(self,name,value):
        with self._lock:
            if value in ('',None):return self.delete(name)
            d=self.load();d[name]=value;self.save(d);return True
    def delete(self,name):
        with self._lock:
            d=self.load()
            if name in d:d.pop(name,None);self.save(d)
            return True

class DurableState(dict):
    def __init__(self,secrets_store,prefix='session:'):super().__init__();self._store=secrets_store;self._prefix=prefix
    def __setitem__(self,key,value):
        super().__setitem__(key,value)
        if str(key).startswith('oidc:'):self._store.set(self._prefix+str(key),value)
    def get(self,key,default=None):
        if key in self:return super().get(key,default)
        if str(key).startswith('oidc:'):return self._store.get(self._prefix+str(key),default)
        return default
    def pop(self,key,default=None):
        if key in self:out=super().pop(key)
        else:out=self._store.get(self._prefix+str(key),default) if str(key).startswith('oidc:') else default
        if str(key).startswith('oidc:'):self._store.delete(self._prefix+str(key))
        return out
    def __contains__(self,key):return dict.__contains__(self,key) or (str(key).startswith('oidc:') and self._store.get(self._prefix+str(key),None) is not None)

class OIDCProvider:
    PRESETS={'google':'https://accounts.google.com','microsoft':'https://login.microsoftonline.com/common/v2.0'}
    PROFILE_SCOPES={'google':'openid profile email https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly','microsoft':'openid profile email offline_access User.Read Calendars.ReadWrite Mail.Read Mail.Send','generic':'openid profile email'}
    def __init__(self,provider='',issuer='',client_id='',client_secret='',redirect_uri='',scopes=''):
        self.provider=provider or 'generic';self.issuer=(issuer or self.PRESETS.get(self.provider,'')).rstrip('/');self.client_id=client_id;self.client_secret=client_secret;self.redirect_uri=redirect_uri;self.scopes=scopes or self.PROFILE_SCOPES.get(self.provider,self.PROFILE_SCOPES['generic']);self.metadata={}
    @property
    def configured(self):return bool(self.issuer and self.client_id and self.redirect_uri)
    async def discover(self):
        if not self.configured:raise RuntimeError('OIDC not configured')
        import httpx
        async with httpx.AsyncClient(timeout=20) as c:r=await c.get(self.issuer+'/.well-known/openid-configuration');r.raise_for_status();self.metadata=r.json();return self.metadata
    async def authorize_url(self,state,challenge,nonce=''):
        from urllib.parse import urlencode
        m=self.metadata or await self.discover();p={'client_id':self.client_id,'redirect_uri':self.redirect_uri,'response_type':'code','scope':self.scopes,'state':state,'code_challenge':challenge,'code_challenge_method':'S256'}
        if nonce:p['nonce']=nonce
        return m['authorization_endpoint']+'?'+urlencode(p)
    async def exchange(self,code,verifier):
        import httpx
        m=self.metadata or await self.discover();d={'grant_type':'authorization_code','code':code,'client_id':self.client_id,'redirect_uri':self.redirect_uri,'code_verifier':verifier}
        if self.client_secret:d['client_secret']=self.client_secret
        async with httpx.AsyncClient(timeout=20) as c:r=await c.post(m['token_endpoint'],data=d);r.raise_for_status();return r.json()
    async def userinfo(self,access_token):
        import httpx
        m=self.metadata or await self.discover();url=m.get('userinfo_endpoint')
        if not url:return {}
        async with httpx.AsyncClient(timeout=20) as c:r=await c.get(url,headers={'Authorization':'Bearer '+access_token});r.raise_for_status();return r.json()
    async def validate_id_token(self,id_token,nonce=''):
        import jwt
        m=self.metadata or await self.discover();header=jwt.get_unverified_header(id_token);alg=str(header.get('alg') or '')
        advertised=m.get('id_token_signing_alg_values_supported') or ['RS256']
        if not alg or alg not in set(str(x) for x in advertised):raise ValueError('OIDC ID token signing algorithm is not allowed by provider metadata')
        jwks=jwt.PyJWKClient(m['jwks_uri']);key=jwks.get_signing_key_from_jwt(id_token);claims=jwt.decode(id_token,key.key,algorithms=[alg],audience=self.client_id,options={'require':['exp','iat','iss','sub']})
        expected=m.get('issuer',self.issuer);iss=claims.get('iss','')
        if '{tenantid}' in expected:expected=expected.replace('{tenantid}',claims.get('tid',''))
        if iss!=expected:raise ValueError('OIDC issuer validation failed')
        if nonce and claims.get('nonce')!=nonce:raise ValueError('OIDC nonce validation failed')
        return claims

def pkce_pair():
    v=secrets.token_urlsafe(64);c=base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b'=').decode();return v,c

class AuthManager:
    def __init__(self,settings,root:Path):
        self.settings=settings;self.secrets=SecretStore(root);self.sessions=DurableState(self.secrets);self.oidc=OIDCProvider(settings.oidc_provider,settings.oidc_issuer,settings.oidc_client_id,settings.oidc_client_secret,settings.oidc_redirect_uri,settings.oidc_scopes)
        if self.oidc.client_id:self.secrets.set('oidc:client_id',self.oidc.client_id)
    @property
    def mode(self):return self.settings.auth_mode
    def mint_session(self,claims):t=secrets.token_urlsafe(48);self.sessions[t]={'claims':claims,'expires':time.time()+self.settings.session_ttl};return t
    def validate_session(self,token):s=self.sessions.get(token);return bool(s and s['expires']>time.time())
