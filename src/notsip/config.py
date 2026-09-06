from pathlib import Path
import json, os
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SECRET_FIELDS={'api_key','event_hmac_secret','pairing_secret','llm_api_key','fallback_llm_api_key','stt_api_key','tts_api_key','email_password','oidc_client_secret','oauth_client_secret','node_shared_secret','brave_api_key'}

class Settings(BaseSettings):
    host:str='127.0.0.1'; port:int=Field(8765,ge=1,le=65535); data_dir:str='./data'; local_timezone:str='Africa/Kigali'; max_tool_rounds:int=Field(10,ge=1,le=100)
    autonomy_level:int=Field(2,ge=0,le=4); self_modify_enabled:bool=False
    api_key:str=''; event_hmac_secret:str=''; pairing_secret:str=''; auth_mode:Literal['api_key','oidc']='api_key'; session_ttl:int=Field(43200,ge=300,le=2592000)
    oidc_provider:str='generic'; oidc_issuer:str=''; oidc_client_id:str=''; oidc_client_secret:str=''; oidc_redirect_uri:str=''; oidc_scopes:str=''
    llm_base_url:str=''; llm_api_key:str=''; llm_model:str=''; fallback_llm_base_url:str=''; fallback_llm_api_key:str=''; fallback_llm_model:str=''
    stt_base_url:str=''; stt_api_key:str=''; stt_model:str=''; stt_language:str=''; stt_stream_url:str=''
    tts_base_url:str=''; tts_api_key:str=''; tts_model:str=''; tts_voice:str='alloy'; tts_format:str='mp3'
    voice_enabled:bool=False; native_voice_enabled:bool=False; voice_sample_rate:int=Field(16000,ge=8000,le=48000); vad_rms_threshold:float=Field(700,ge=1); vad_silence_blocks:int=Field(8,ge=1,le=100); wake_word:str=''
    vision_enabled:bool=True; perception_enabled:bool=True; perception_interval:int=Field(10,ge=2,le=3600); brave_api_key:str=''; browser_enabled:bool=True
    perception_screen_enabled:bool=False; health_interval:int=Field(15,ge=5,le=3600); checkpoint_interval:int=Field(300,ge=30,le=86400); proactive_interval:int=Field(60,ge=15,le=86400); memory_maintenance_interval:int=Field(900,ge=60,le=604800)
    smtp_host:str=''; smtp_port:int=Field(587,ge=1,le=65535); imap_host:str=''; email_username:str=''; email_password:str=''; oauth_authorize_url:str=''; oauth_token_url:str=''; oauth_client_id:str=''; oauth_client_secret:str=''; oauth_redirect_uri:str=''; oauth_scopes:str=''
    android_poll_seconds:int=Field(3,ge=1,le=3600); node_lease_seconds:int=Field(90,ge=15,le=86400); node_shared_secret:str=''
    database_url:str='sqlite:///data/notsip.db'; github_update_enabled:bool=True; github_repository:str='Notsip-995/NOTSIP-Platform'
    log_level:Literal['DEBUG','INFO','WARNING','ERROR']='INFO'; log_max_bytes:int=Field(10485760,ge=1024,le=1073741824); log_backup_count:int=Field(5,ge=1,le=50); open_browser:bool=True; node_name:str='NOTSIP'
    model_config=SettingsConfigDict(env_prefix='NOTSIP_',env_file='.env',extra='ignore',validate_assignment=True)
    def ensure(self):
        root=Path(self.data_dir);root.mkdir(parents=True,exist_ok=True)
        for name in ('workspace','screenshots','audio','perception','recovery','runtime','backups','updates'):(root/name).mkdir(parents=True,exist_ok=True)
settings=Settings()
try:
    cfg=Path(settings.data_dir)/'config.json'
    if cfg.exists():
        data=json.loads(cfg.read_text(encoding='utf-8')).get('settings',{})
        for k,v in data.items():
            if k not in SECRET_FIELDS and k in Settings.model_fields and ('NOTSIP_'+k.upper()) not in os.environ:setattr(settings,k,v)
except Exception:pass
settings.ensure()
try:
    from .security import SecretStore
    _secret_store=SecretStore(Path(settings.data_dir).resolve())
    for _name in SECRET_FIELDS:
        if not getattr(settings,_name,None):
            _v=_secret_store.get('NOTSIP_'+_name.upper())
            if _v:setattr(settings,_name,_v)
except Exception:pass
