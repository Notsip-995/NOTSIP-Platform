from __future__ import annotations
import base64, email.policy
from email.message import EmailMessage
from urllib.parse import quote
import httpx

class OAuthService:
    PROFILES={
        'google':{'scopes':'openid profile email https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly','calendar':'https://www.googleapis.com/calendar/v3/calendars/primary/events','mail':'https://gmail.googleapis.com/gmail/v1/users/me/messages','calendar_scope':'https://www.googleapis.com/auth/calendar','mail_scope':'https://www.googleapis.com/auth/gmail.send','token':'https://oauth2.googleapis.com/token','revoke':'https://oauth2.googleapis.com/revoke'},
        'microsoft':{'scopes':'openid profile email offline_access User.Read Calendars.ReadWrite Mail.Read Mail.Send','calendar':'https://graph.microsoft.com/v1.0/me/calendar/events','mail':'https://graph.microsoft.com/v1.0/me/messages','calendar_scope':'Calendars.ReadWrite','mail_scope':'Mail.Send','token':'https://login.microsoftonline.com/common/oauth2/v2.0/token'},
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
        item=self._account(provider,account_id);tokens=self.accounts.tokens(item['id']);return tokens.get('access_token',''),item
    def _scopes(self,item):return set(str(item.get('scopes','')).replace(',',' ').split())
    def _require_scope(self,provider,item,kind):
        required=self.PROFILES[provider].get(f'{kind}_scope','')
        if required not in self._scopes(item):raise PermissionError(f'{provider} OAuth account lacks required scope: {required}')
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
    async def _request(self,provider,method,path,account_id=None,**kwargs):
        token,item=self._token(provider,account_id)
        if not token:raise RuntimeError(f'{provider} account is not authorized')
        extra_headers=dict(kwargs.pop('headers',{}) or {})
        async with httpx.AsyncClient(timeout=30) as c:
            def headers_for(current):return {'Authorization':'Bearer '+current,'Accept':'application/json',**extra_headers}
            r=await c.request(method,path,headers=headers_for(token),**kwargs)
            if r.status_code==401:
                await self.refresh(provider,item['id']);token,_=self._token(provider,item['id']);r=await c.request(method,path,headers=headers_for(token),**kwargs)
            if r.status_code not in (200,201,202,204):r.raise_for_status()
            if r.status_code==204 or not r.content:return {'status':'SUCCESS','provider_status':r.status_code}
            data=r.json();return {'status':'SUCCESS','provider_status':r.status_code,'data':data}
    async def calendar_create(self,provider,title,start,end,description='',location='',timezone='UTC',account_id=None):
        if provider not in self.PROFILES:raise ValueError('unsupported OAuth provider')
        token,item=self._token(provider,account_id);self._require_scope(provider,item,'calendar')
        if provider=='google':body={'summary':title,'description':description,'location':location,'start':{'dateTime':start,'timeZone':timezone},'end':{'dateTime':end,'timeZone':timezone}}
        else:body={'subject':title,'body':{'contentType':'Text','content':description},'location':{'displayName':location},'start':{'dateTime':start,'timeZone':timezone},'end':{'dateTime':end,'timeZone':timezone}}
        return await self._request(provider,'POST',self.PROFILES[provider]['calendar'],item['id'],json=body)
    async def calendar_update(self,provider,event_id,changes,account_id=None):
        if provider not in self.PROFILES:raise ValueError('unsupported OAuth provider')
        token,item=self._token(provider,account_id);self._require_scope(provider,item,'calendar');eid=str(event_id).strip()
        if not eid:raise ValueError('event_id is required')
        body=dict(changes or {})
        if provider=='microsoft' and 'title' in body:body['subject']=body.pop('title')
        if provider=='google' and 'title' in body:body={'summary':body['title'],**{k:v for k,v in body.items() if k!='title'}}
        path=self.PROFILES[provider]['calendar'].rstrip('/')+'/'+quote(eid,safe='')
        return await self._request(provider,'PATCH' if provider=='microsoft' else 'PUT',path,item['id'],json=body)
    async def calendar_delete(self,provider,event_id,account_id=None):
        if provider not in self.PROFILES:raise ValueError('unsupported OAuth provider')
        token,item=self._token(provider,account_id);self._require_scope(provider,item,'calendar');eid=str(event_id).strip()
        if not eid:raise ValueError('event_id is required')
        return await self._request(provider,'DELETE',self.PROFILES[provider]['calendar'].rstrip('/')+'/'+quote(eid,safe=''),item['id'])
    async def send_mail(self,provider,to,subject,body,account_id=None):
        if provider not in self.PROFILES:raise ValueError('unsupported OAuth provider')
        token,item=self._token(provider,account_id);self._require_scope(provider,item,'mail')
        if provider=='google':
            msg=EmailMessage(policy=email.policy.SMTP);msg['To']=to;msg['Subject']=subject;msg['From']=item.get('email','');msg.set_content(body);raw=base64.urlsafe_b64encode(msg.as_bytes()).decode().rstrip('=');payload={'raw':raw};result=await self._request(provider,'POST','https://gmail.googleapis.com/gmail/v1/users/me/messages/send',item['id'],json=payload)
        else:
            payload={'message':{'subject':subject,'body':{'contentType':'Text','content':body},'toRecipients':[{'emailAddress':{'address':to}}]}};result=await self._request(provider,'POST','https://graph.microsoft.com/v1.0/me/sendMail',item['id'],json=payload)
        result['status']='PARTIAL_SUCCESS';result['verified']=False;result['note']='Provider accepted the send request; recipient delivery was not independently verified.';return result
    async def refresh(self,provider,account_id=None):
        if provider not in self.PROFILES:raise ValueError('unsupported OAuth provider')
        item=self._account(provider,account_id);tokens=self.accounts.tokens(item['id']);refresh=tokens.get('refresh_token','');client_id=self.secrets.get(f'{provider}:client_id','') or self.secrets.get('oidc:client_id','')
        if not refresh or not client_id:raise RuntimeError(f'{provider} refresh token or client id unavailable')
        async with httpx.AsyncClient(timeout=30) as c:r=await c.post(self.PROFILES[provider]['token'],data={'grant_type':'refresh_token','refresh_token':refresh,'client_id':client_id});r.raise_for_status();new=r.json()
        self.accounts.save_tokens(item['id'],new);return new
    async def revoke(self,provider,account_id=None):
        if provider not in self.PROFILES:raise ValueError('unsupported OAuth provider')
        item=self._account(provider,account_id);tokens=self.accounts.tokens(item['id']);access=tokens.get('access_token','');refresh=tokens.get('refresh_token','')
        if not access and not refresh:return {'status':'ALREADY_REVOKED','account_id':item['id'],'provider':provider}
        if provider=='google':
            connected=self.accounts.for_provider('google')
            if len(connected)>1:return {'status':'PROVIDER_REVOCATION_BLOCKED_MULTI_ACCOUNT','account_id':item['id'],'provider':provider,'connected_accounts':len(connected),'reason':'Google project-level revocation could invalidate another connected account; local credentials were retained'}
            token=refresh or access
            async with httpx.AsyncClient(timeout=30) as c:r=await c.post(self.PROFILES['google']['revoke'],params={'token':token})
            if r.status_code not in (200,400):r.raise_for_status()
            if r.status_code==400:return {'status':'PROVIDER_TOKEN_ALREADY_INVALID','account_id':item['id'],'provider':provider,'provider_status':400}
            return {'status':'PROVIDER_REVOKED','account_id':item['id'],'provider':provider,'provider_status':r.status_code}
        return {'status':'PROVIDER_REVOCATION_UNAVAILABLE','account_id':item['id'],'provider':provider,'reason':'Microsoft delegated-token revocation is not safely available through the configured integration without broader user-session revocation'}
    def save_tokens(self,provider,tokens,account_id=None):
        item=self._account(provider,account_id);return self.accounts.save_tokens(item['id'],tokens)
    def profile(self,provider):return self.PROFILES.get(provider,{'scopes':''})
