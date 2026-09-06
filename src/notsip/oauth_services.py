from __future__ import annotations
import httpx

class OAuthService:
    PROFILES={
        'google':{'scopes':'openid profile email https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/gmail.readonly','calendar':'https://www.googleapis.com/calendar/v3/calendars/primary/events','mail':'https://gmail.googleapis.com/gmail/v1/users/me/messages','token':'https://oauth2.googleapis.com/token','revoke':'https://oauth2.googleapis.com/revoke'},
        'microsoft':{'scopes':'openid profile email offline_access User.Read Calendars.Read Mail.Read','calendar':'https://graph.microsoft.com/v1.0/me/calendar/events','mail':'https://graph.microsoft.com/v1.0/me/messages','token':'https://login.microsoftonline.com/common/oauth2/v2.0/token','revoke':'https://login.microsoftonline.com/common/oauth2/v2.0/logout'},
    }
    def __init__(self,secrets,accounts=None):self.secrets=secrets;self.accounts=accounts
    def _account(self,provider,account_id=None):
        if account_id:
            if not self.accounts:raise RuntimeError('account store unavailable')
            item=self.accounts.get(account_id)
            if not item or item.get('provider')!=provider or item.get('status')!='CONNECTED':raise RuntimeError('OAuth account not available')
            return item
        if not self.accounts:raise RuntimeError('account selection required')
        matches=self.accounts.for_provider(provider)
        if len(matches)==1:return matches[0]
        if not matches:raise RuntimeError(f'{provider} account is not authorized')
        raise RuntimeError(f'multiple {provider} accounts are connected; specify account_id')
    def _token(self,provider,account_id=None):
        item=self._account(provider,account_id)
        tokens=self.accounts.tokens(item['id'])
        return tokens.get('access_token',''),item
    async def _get(self,provider,path,account_id=None):
        if provider not in self.PROFILES:raise ValueError('unsupported OAuth provider')
        token,item=self._token(provider,account_id)
        if not token:raise RuntimeError(f'{provider} account is not authorized')
        async with httpx.AsyncClient(timeout=30) as c:
            r=await c.get(self.PROFILES[provider][path],headers={'Authorization':'Bearer '+token,'Accept':'application/json'})
            if r.status_code==401:
                await self.refresh(provider,item['id']);token,_=self._token(provider,item['id']);r=await c.get(self.PROFILES[provider][path],headers={'Authorization':'Bearer '+token,'Accept':'application/json'})
            r.raise_for_status();return r.json()
    async def calendar(self,provider,account_id=None):return await self._get(provider,'calendar',account_id)
    async def mail(self,provider,account_id=None):return await self._get(provider,'mail',account_id)
    async def refresh(self,provider,account_id=None):
        if provider not in self.PROFILES:raise ValueError('unsupported OAuth provider')
        item=self._account(provider,account_id);tokens=self.accounts.tokens(item['id']);refresh=tokens.get('refresh_token','');client_id=self.secrets.get(f'{provider}:client_id','') or self.secrets.get('oidc:client_id','')
        if not refresh or not client_id:raise RuntimeError(f'{provider} refresh token or client id unavailable')
        async with httpx.AsyncClient(timeout=30) as c:
            r=await c.post(self.PROFILES[provider]['token'],data={'grant_type':'refresh_token','refresh_token':refresh,'client_id':client_id});r.raise_for_status();new=r.json()
        self.accounts.save_tokens(item['id'],new);return new
    def save_tokens(self,provider,tokens,account_id=None):
        item=self._account(provider,account_id)
        return self.accounts.save_tokens(item['id'],tokens)
    def profile(self,provider):return self.PROFILES.get(provider,{'scopes':''})
