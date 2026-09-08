from __future__ import annotations
import time, uuid

class AccountStore:
    def __init__(self,secrets):self.secrets=secrets
    def _accounts(self):return self.secrets.get('oauth:accounts',{}) or {}
    def _token_key(self,account_id):return f'oauth:tokens:{account_id}'
    def upsert(self,provider,subject,email='',scopes='',token_meta=None):
        d=self._accounts();key=f'{provider}:{subject or uuid.uuid4().hex}';d[key]={'id':key,'provider':provider,'subject':subject,'email':email,'scopes':scopes,'token_meta':token_meta or {},'connected_at':d.get(key,{}).get('connected_at',time.time()),'updated_at':time.time(),'status':'CONNECTED'};self.secrets.set('oauth:accounts',d);return d[key]
    def list(self):return list(self._accounts().values())
    def get(self,account_id):return self._accounts().get(account_id)
    def for_provider(self,provider):return [x for x in self.list() if x.get('provider')==provider and x.get('status')=='CONNECTED']
    def save_tokens(self,account_id,tokens):
        allowed={'access_token','refresh_token','expires_in','expires_at','token_type','scope','id_token'}
        incoming={k:v for k,v in tokens.items() if k in allowed and v not in (None,'')}
        current=self.tokens(account_id)
        merged=dict(current);merged.update(incoming)
        self.secrets.set(self._token_key(account_id),merged)
        return {'account_id':account_id,'stored':sorted(merged)}
    def tokens(self,account_id):return self.secrets.get(self._token_key(account_id),{}) or {}
    def disconnect(self,account_id):
        d=self._accounts();item=d.get(account_id)
        if item:
            item['status']='DISCONNECTED';item['disconnected_at']=time.time();item['updated_at']=time.time();self.secrets.set('oauth:accounts',d);self.secrets.set(self._token_key(account_id),{})
        return item
    def mark_expired(self,account_id):
        d=self._accounts();item=d.get(account_id)
        if item:item['status']='EXPIRED';item['updated_at']=time.time();self.secrets.set('oauth:accounts',d)
        return item
    def scopes(self,account_id):
        item=self.get(account_id);return item.get('scopes','') if item else ''
