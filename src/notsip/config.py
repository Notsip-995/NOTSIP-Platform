from pathlib import Path
from pydantic_settings import BaseSettings,SettingsConfigDict
class Settings(BaseSettings):
    host:str='127.0.0.1';port:int=8765;data_dir:str='./data';local_timezone:str='Africa/Kigali';max_tool_rounds:int=10;autonomy_level:int=2;api_key:str='';event_hmac_secret:str='';pairing_secret:str='';llm_base_url:str='';llm_api_key:str='';llm_model:str='';fallback_llm_base_url:str='';fallback_llm_api_key:str='';fallback_llm_model:str='';brave_api_key:str='';browser_enabled:bool=True;smtp_host:str='';smtp_port:int=587;imap_host:str='';email_username:str='';email_password:str='';oauth_authorize_url:str='';oauth_token_url:str='';oauth_client_id:str='';oauth_client_secret:str='';oauth_redirect_uri:str='';oauth_scopes:str='';android_poll_seconds:int=3
    model_config=SettingsConfigDict(env_prefix='NOTSIP_',env_file='.env',extra='ignore')
    def ensure(self):
        r=Path(self.data_dir);r.mkdir(parents=True,exist_ok=True);(r/'workspace').mkdir(parents=True,exist_ok=True);(r/'screenshots').mkdir(parents=True,exist_ok=True)
settings=Settings();settings.ensure()
