from __future__ import annotations
import time,uuid
from .actor_context import current_actor

class AccountStore:
    def __init__(self,secrets):self.secrets=secrets
    def _accounts(self):return self.secrets.get('oauth:accounts',{}) or {}
    def _token_key(self,account_id):return f'oauth:tokens:{account_id}'
    def _owner(self,owner=None):return str(owner or current_actor()).strip() or 'primary-user'
    def upsert(self,provider,subject,email='',scopes='',token_meta=None,owner=None):
        owner=self._owner(owner);d=self._accounts();subject=str(subject or '').strip();key=f'{owner}:{provider}:{subject or uuid.uuid4().hex}';existing=d.get(key,{})
        d[key]={'id':key,'owner':owner,'provider':provider,'subject':subject,'email':email,'scopes':scopes,'token_meta':token_meta or {},'connected_at':existing.get('connected_at',time.time()),'updated_at':time.time(),'status':'CONNECTED'};self.secrets.set('oauth:accounts',d);return d[key]
    def list(self,owner=None):
        owner=self._owner(owner);return [x for x in self._accounts().values() if x.get('owner','primary-user')==owner]
    def get(self,account_id,owner=None):
        owner=self._owner(owner);item=self._accounts().get(account_id)
        return item if item and item.get('owner','primary-user')==owner else None
    def for_provider(self,provider,owner=None):return [x for x in self.list(owner) if x.get('provider')==provider and x.get('status')=='CONNECTED']
    def save_tokens(self,account_id,tokens,owner=None):
        item=self.get(account_id,owner)
        if not item:raise KeyError(account_id)
        allowed={'access_token','refresh_token','expires_in','expires_at','token_type','scope','id_token'};incoming={k:v for k,v in tokens.items() if k in allowed and v not in (None,'')};current=self.tokens(account_id,owner);merged=dict(current);merged.update(incoming);self.secrets.set(self._token_key(account_id),merged);return {'account_id':account_id,'stored':sorted(merged)}
    def tokens(self,account_id,owner=None):return self.secrets.get(self._token_key(account_id),{}) if self.get(account_id,owner) else {}
    def disconnect(self,account_id,owner=None):
        d=self._accounts();item=self.get(account_id,owner)
        if item:
            item['status']='DISCONNECTED';item['disconnected_at']=time.time();item['updated_at']=time.time();d[account_id]=item;self.secrets.set('oauth:accounts',d);self.secrets.set(self._token_key(account_id),{})
        return item
    def mark_expired(self,account_id,owner=None):
        d=self._accounts();item=self.get(account_id,owner)
        if item:item['status']='EXPIRED';item['updated_at']=time.time();d[account_id]=item;self.secrets.set('oauth:accounts',d)
        return item
    def scopes(self,account_id,owner=None):
        item=self.get(account_id,owner);return item.get('scopes','') if item else ''
