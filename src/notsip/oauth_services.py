from __future__ import annotations
import httpx
class OAuthService:
    PROFILES={
        'google':{'scopes':'openid profile email https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/gmail.readonly','calendar':'https://www.googleapis.com/calendar/v3/calendars/primary/events','mail':'https://gmail.googleapis.com/gmail/v1/users/me/messages','token':'https://oauth2.googleapis.com/token'},
        'microsoft':{'scopes':'openid profile email offline_access User.Read Calendars.Read Mail.Read','calendar':'https://graph.microsoft.com/v1.0/me/calendar/events','mail':'https://graph.microsoft.com/v1.0/me/messages','token':'https://login.microsoftonline.com/common/oauth2/v2.0/token'},
    }
    def __init__(self,secrets):self.secrets=secrets
    def _token(self,provider):
        token=self.secrets.get(f'{provider}:access_token','')
        if token:return token
        saved=self.secrets.get('oidc:tokens',{})
        return saved.get('access_token','') if self.secrets.get('oidc:provider','')==provider else ''
    async def _get(self,provider,path):
        if provider not in self.PROFILES:raise ValueError('unsupported OAuth provider')
        token=self._token(provider)
        if not token:raise RuntimeError(f'{provider} account is not authorized')
        async with httpx.AsyncClient(timeout=30) as c:
            r=await c.get(self.PROFILES[provider][path],headers={'Authorization':'Bearer '+token,'Accept':'application/json'});r.raise_for_status();return r.json()
    async def calendar(self,provider):return await self._get(provider,'calendar')
    async def mail(self,provider):return await self._get(provider,'mail')
    async def refresh(self,provider):
        if provider not in self.PROFILES:raise ValueError('unsupported OAuth provider')
        refresh=self.secrets.get(f'{provider}:refresh_token','') or self.secrets.get('oidc:tokens',{}).get('refresh_token','');client_id=self.secrets.get(f'{provider}:client_id','')
        if not refresh or not client_id:raise RuntimeError(f'{provider} refresh token or client id unavailable')
        async with httpx.AsyncClient(timeout=30) as c:
            r=await c.post(self.PROFILES[provider]['token'],data={'grant_type':'refresh_token','refresh_token':refresh,'client_id':client_id});r.raise_for_status();tokens=r.json()
        self.save_tokens(provider,tokens);return tokens
    def save_tokens(self,provider,tokens):
        if tokens.get('access_token'):self.secrets.set(f'{provider}:access_token',tokens['access_token'])
        if tokens.get('refresh_token'):self.secrets.set(f'{provider}:refresh_token',tokens['refresh_token'])
        if provider:self.secrets.set(f'{provider}:client_id',self.secrets.get('oidc:client_id',''))
        return {'provider':provider,'stored':sorted(k for k in tokens if 'token' in k)}
    def profile(self,provider):return self.PROFILES.get(provider,{'scopes':''})
