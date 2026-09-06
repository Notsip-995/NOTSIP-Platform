from __future__ import annotations
import json
import httpx

class OAuthService:
    PROFILES={
        'google': {
            'scopes':'openid profile email https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/gmail.readonly',
            'calendar':'https://www.googleapis.com/calendar/v3/calendars/primary/events',
            'mail':'https://gmail.googleapis.com/gmail/v1/users/me/messages',
        },
        'microsoft': {
            'scopes':'openid profile email offline_access User.Read Calendars.Read Mail.Read',
            'calendar':'https://graph.microsoft.com/v1.0/me/calendar/events',
            'mail':'https://graph.microsoft.com/v1.0/me/messages',
        },
    }
    def __init__(self,secrets): self.secrets=secrets
    async def _get(self,provider,path):
        token=self.secrets.get(f'{provider}:access_token','')
        if not token: raise RuntimeError(f'{provider} account is not authorized')
        url=self.PROFILES[provider][path]
        async with httpx.AsyncClient(timeout=30) as c:
            r=await c.get(url,headers={'Authorization':'Bearer '+token,'Accept':'application/json'});r.raise_for_status();return r.json()
    async def calendar(self,provider):return await self._get(provider,'calendar')
    async def mail(self,provider):return await self._get(provider,'mail')
    def save_tokens(self,provider,tokens):
        if tokens.get('access_token'):self.secrets.set(f'{provider}:access_token',tokens['access_token'])
        if tokens.get('refresh_token'):self.secrets.set(f'{provider}:refresh_token',tokens['refresh_token'])
        return {'provider':provider,'stored':sorted(k for k in tokens if 'token' in k)}
    def profile(self,provider):return self.PROFILES.get(provider,{'scopes':''})
