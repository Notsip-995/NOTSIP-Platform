from __future__ import annotations
import time, uuid
class AccountStore:
    def __init__(self,secrets):self.secrets=secrets
    def _accounts(self):return self.secrets.get('oauth:accounts',{}) or {}
    def upsert(self,provider,subject,email='',scopes='',token_meta=None):
        d=self._accounts();key=f'{provider}:{subject or uuid.uuid4().hex}';d[key]={'id':key,'provider':provider,'subject':subject,'email':email,'scopes':scopes,'token_meta':token_meta or {},'connected_at':d.get(key,{}).get('connected_at',time.time()),'updated_at':time.time()};self.secrets.set('oauth:accounts',d);return d[key]
    def list(self):return list(self._accounts().values())
    def get(self,account_id):return self._accounts().get(account_id)
    def disconnect(self,account_id):
        d=self._accounts();item=d.pop(account_id,None)
        if item:self.secrets.set('oauth:accounts',d)
        return item
    def scopes(self,account_id):
        item=self.get(account_id);return item.get('scopes','') if item else ''
