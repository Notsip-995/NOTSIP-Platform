from pathlib import Path
import json, os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    host:str='127.0.0.1'; port:int=8765; data_dir:str='./data'; local_timezone:str='Africa/Kigali'; max_tool_rounds:int=10
    autonomy_level:int=2; self_modify_enabled:bool=False
    api_key:str=''; event_hmac_secret:str=''; pairing_secret:str=''; auth_mode:str='api_key'; session_ttl:int=43200
    oidc_provider:str='generic'; oidc_issuer:str=''; oidc_client_id:str=''; oidc_client_secret:str=''; oidc_redirect_uri:str=''; oidc_scopes:str=''
    llm_base_url:str=''; llm_api_key:str=''; llm_model:str=''; fallback_llm_base_url:str=''; fallback_llm_api_key:str=''; fallback_llm_model:str=''
    stt_base_url:str=''; stt_api_key:str=''; stt_model:str=''; stt_language:str=''; tts_base_url:str=''; tts_api_key:str=''; tts_model:str=''; tts_voice:str='alloy'; tts_format:str='mp3'
    vision_enabled:bool=True; perception_enabled:bool=True; perception_interval:int=10; brave_api_key:str=''; browser_enabled:bool=True
    perception_screen_enabled:bool=False; health_interval:int=15; checkpoint_interval:int=300; proactive_interval:int=60; memory_maintenance_interval:int=900
    smtp_host:str=''; smtp_port:int=587; imap_host:str=''; email_username:str=''; email_password:str=''; oauth_authorize_url:str=''; oauth_token_url:str=''; oauth_client_id:str=''; oauth_client_secret:str=''; oauth_redirect_uri:str=''; oauth_scopes:str=''
    android_poll_seconds:int=3; node_lease_seconds:int=90; node_shared_secret:str=''
    database_url:str='sqlite:///data/notsip.db'; github_update_enabled:bool=True; github_repository:str='Notsip-995/NOTSIP-Platform'
    model_config=SettingsConfigDict(env_prefix='NOTSIP_',env_file='.env',extra='ignore')
    def ensure(self):
        root=Path(self.data_dir);root.mkdir(parents=True,exist_ok=True)
        for name in ('workspace','screenshots','audio','perception','recovery','runtime','backups','updates'):(root/name).mkdir(parents=True,exist_ok=True)
settings=Settings()
try:
    cfg=Path(settings.data_dir)/'config.json'
    if cfg.exists():
        data=json.loads(cfg.read_text(encoding='utf-8')).get('settings',{})
        secret_fields={'api_key','event_hmac_secret','pairing_secret','llm_api_key','fallback_llm_api_key','stt_api_key','tts_api_key','email_password','oidc_client_secret','oauth_client_secret','node_shared_secret'}
        for k,v in data.items():
            if k not in secret_fields and k in Settings.model_fields and ('NOTSIP_'+k.upper()) not in os.environ:setattr(settings,k,v)
except Exception:pass
settings.ensure()
try:
    from .security import SecretStore
    _secret_store=SecretStore(Path(settings.data_dir).resolve())
    for _name in ('api_key','event_hmac_secret','pairing_secret','llm_api_key','fallback_llm_api_key','stt_api_key','tts_api_key','email_password','oidc_client_secret','oauth_client_secret','node_shared_secret'):
        if not getattr(settings,_name,None):
            _v=_secret_store.get('NOTSIP_'+_name.upper())
            if _v:setattr(settings,_name,_v)
except Exception:pass
