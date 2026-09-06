from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    host:str='127.0.0.1'; port:int=8765; data_dir:str='./data'; local_timezone:str='Africa/Kigali'; max_tool_rounds:int=10
    autonomy_level:int=2; self_modify_enabled:bool=False
    api_key:str=''; event_hmac_secret:str=''; pairing_secret:str=''
    auth_mode:str='api_key'; session_ttl:int=43200
    oidc_issuer:str=''; oidc_client_id:str=''; oidc_client_secret:str=''; oidc_redirect_uri:str=''; oidc_scopes:str='openid profile email'
    llm_base_url:str=''; llm_api_key:str=''; llm_model:str=''; fallback_llm_base_url:str=''; fallback_llm_api_key:str=''; fallback_llm_model:str=''
    stt_base_url:str=''; stt_api_key:str=''; stt_model:str=''; stt_language:str=''; tts_base_url:str=''; tts_api_key:str=''; tts_model:str=''; tts_voice:str='alloy'; tts_format:str='mp3'
    vision_enabled:bool=True; perception_enabled:bool=True; perception_interval:int=10
    brave_api_key:str=''; browser_enabled:bool=True
    smtp_host:str=''; smtp_port:int=587; imap_host:str=''; email_username:str=''; email_password:str=''
    oauth_authorize_url:str=''; oauth_token_url:str=''; oauth_client_id:str=''; oauth_client_secret:str=''; oauth_redirect_uri:str=''; oauth_scopes:str=''
    android_poll_seconds:int=3; node_lease_seconds:int=90; node_shared_secret:str=''
    model_config=SettingsConfigDict(env_prefix='NOTSIP_',env_file='.env',extra='ignore')
    def ensure(self):
        root=Path(self.data_dir); root.mkdir(parents=True,exist_ok=True); (root/'workspace').mkdir(parents=True,exist_ok=True); (root/'screenshots').mkdir(parents=True,exist_ok=True); (root/'audio').mkdir(parents=True,exist_ok=True); (root/'perception').mkdir(parents=True,exist_ok=True)
settings=Settings(); settings.ensure()
