from pathlib import Path
import json, os, sys, ipaddress
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SECRET_FIELDS={'api_key','event_hmac_secret','pairing_secret','llm_api_key','fallback_llm_api_key','stt_api_key','tts_api_key','email_password','oidc_client_secret','oauth_client_secret','node_shared_secret','brave_api_key','remote_compute_token','remote_sensing_token','home_adapter_token','biometric_adapter_token','flight_planning_token','business_admin_token','speaker_identity_token'}
CONFIG_LOAD_ERROR='';SECRET_LOAD_ERROR=''
DEFAULT_CAPABILITY_LEVELS={'TIME':0,'COMPUTE':0,'INTELLIGENCE':0,'INTERNET_SEARCH':0,'READ_FILES':0,'READ_CALENDAR':1,'WRITE_CALENDAR':2,'READ_EMAIL':1,'MEDIA':1,'PERCEPTION':1,'SYSTEM_DIAGNOSTICS':0,'WRITE_FILES':2,'DELETE_FILES':4,'CONTROL_COMPUTER':3,'ANDROID_CONTROL':3,'SEND_EMAIL':3,'SELF_MAINTENANCE':4,'CONTROL_HOME':3,'CONTROL_SERVER':4,'EXECUTE_CODE':4,'CODE_EXECUTION':4,'SIMULATION':4,'CONTROL_ROBOTICS':4,'ACCESS_CAMERA':2,'ACCESS_MICROPHONE':2,'READ_WEATHER':0,'READ_NEWS':0,'NAVIGATION':1,'FLIGHT_PLANNING':3,'MANAGE_ACCOUNTS':3,'BUSINESS_ADMIN':3}

def _default_data_dir():
    if getattr(sys,'frozen',False):return str(Path(os.getenv('LOCALAPPDATA',Path.home()))/'NOTSIP'/'data')
    return './data'

def _is_loopback_host(host):
    value=str(host or '').strip().lower()
    if value in {'localhost','localhost.localdomain'}:return True
    try:return ipaddress.ip_address(value).is_loopback
    except ValueError:return False

class Settings(BaseSettings):
    host:str='127.0.0.1'; port:int=Field(8765,ge=1,le=65535); data_dir:str=_default_data_dir(); local_timezone:str='Africa/Kigali'; max_tool_rounds:int=Field(10,ge=1,le=100)
    autonomy_level:int=Field(2,ge=0,le=4); self_modify_enabled:bool=False; capability_levels:dict[str,int]=Field(default_factory=lambda:dict(DEFAULT_CAPABILITY_LEVELS))
    api_key:str=''; event_hmac_secret:str=''; pairing_secret:str=''; auth_mode:Literal['api_key','oidc']='api_key'; session_ttl:int=Field(43200,ge=300,le=2592000)
    oidc_provider:str='generic'; oidc_issuer:str=''; oidc_client_id:str=''; oidc_client_secret:str=''; oidc_redirect_uri:str=''; oidc_scopes:str=''
    llm_base_url:str=''; llm_api_key:str=''; llm_model:str=''; fallback_llm_base_url:str=''; fallback_llm_api_key:str=''; fallback_llm_model:str=''
    stt_base_url:str=''; stt_api_key:str=''; stt_model:str=''; stt_language:str=''; stt_stream_url:str=''
    tts_base_url:str=''; tts_api_key:str=''; tts_model:str=''; tts_language:str=''; tts_voice:str='alloy'; tts_format:str='mp3'
    voice_enabled:bool=False; native_voice_enabled:bool=False; voice_sample_rate:int=Field(16000,ge=8000,le=48000); vad_rms_threshold:float=Field(700,ge=1); vad_silence_blocks:int=Field(8,ge=1,le=100); wake_word:str=''
    vision_enabled:bool=True; perception_enabled:bool=True; perception_interval:int=Field(10,ge=2,le=3600); brave_api_key:str=''; browser_enabled:bool=True
    perception_screen_enabled:bool=False; health_interval:int=Field(15,ge=5,le=3600); checkpoint_interval:int=Field(300,ge=30,le=86400); proactive_interval:int=Field(60,ge=15,le=86400); memory_maintenance_interval:int=Field(900,ge=60,le=604800)
    smtp_host:str=''; smtp_port:int=Field(587,ge=1,le=65535); imap_host:str=''; email_username:str=''; email_password:str=''; oauth_authorize_url:str=''; oauth_token_url:str=''; oauth_client_id:str=''; oauth_client_secret:str=''; oauth_redirect_uri:str=''; oauth_scopes:str=''
    android_poll_seconds:int=Field(3,ge=1,le=3600); node_lease_seconds:int=Field(90,ge=15,le=86400); node_shared_secret:str=''
    remote_compute_url:str=''; remote_sensing_url:str=''; home_adapter_url:str=''; biometric_adapter_url:str=''; flight_planning_url:str=''; business_admin_url:str=''; speaker_identity_url:str=''
    database_url:str=''; github_update_enabled:bool=True; github_repository:str='Notsip-995/NOTSIP-Platform'; windows_publisher_thumbprint:str=''
    log_level:Literal['DEBUG','INFO','WARNING','ERROR']='INFO'; log_max_bytes:int=Field(10485760,ge=1024,le=1073741824); log_backup_count:int=Field(5,ge=1,le=50); open_browser:bool=True; node_name:str='NOTSIP'
    model_config=SettingsConfigDict(env_prefix='NOTSIP_',env_file='.env',extra='ignore',validate_assignment=True)
    def ensure(self):
        self.capability_levels={k:max(0,min(4,int(v))) for k,v in (self.capability_levels or DEFAULT_CAPABILITY_LEVELS).items()}
        if not _is_loopback_host(self.host):
            if self.auth_mode=='api_key' and not self.api_key:raise RuntimeError('Remote binding requires NOTSIP_API_KEY or OIDC authentication; refusing unauthenticated non-loopback bind')
            if self.auth_mode=='oidc' and not (self.oidc_issuer and self.oidc_client_id and self.oidc_redirect_uri):raise RuntimeError('Remote binding with OIDC requires oidc_issuer, oidc_client_id and oidc_redirect_uri')
        root=Path(self.data_dir);root.mkdir(parents=True,exist_ok=True)
        for name in ('workspace','screenshots','audio','perception','recovery','runtime','backups','updates'):(root/name).mkdir(parents=True,exist_ok=True)

settings=Settings()
cfg=Path(settings.data_dir)/'config.json'
if cfg.exists():
    try:
        raw=json.loads(cfg.read_text(encoding='utf-8'))
        if not isinstance(raw,dict) or not isinstance(raw.get('settings',{}),dict):raise ValueError('persisted configuration must contain an object-valued settings field')
        data=raw['settings']
        for k,v in data.items():
            if k in Settings.model_fields and k not in SECRET_FIELDS and ('NOTSIP_'+k.upper()) not in os.environ:setattr(settings,k,v)
    except Exception as exc:
        CONFIG_LOAD_ERROR=f'{type(exc).__name__}: {exc}'
        raise RuntimeError(f'failed to load persisted NOTSIP configuration: {CONFIG_LOAD_ERROR}') from exc
try:
    Path(settings.data_dir).mkdir(parents=True,exist_ok=True)
    from .security import SecretStore
    _secret_store=SecretStore(Path(settings.data_dir).resolve())
    for _name in SECRET_FIELDS:
        if not getattr(settings,_name,None):
            _v=_secret_store.get('NOTSIP_'+_name.upper())
            if _v:setattr(settings,_name,_v)
    if not settings.database_url:settings.database_url='sqlite:///data/notsip.db'
    settings.ensure()
except Exception as exc:
    SECRET_LOAD_ERROR=f'{type(exc).__name__}: {exc}'
    raise RuntimeError(f'failed to initialize NOTSIP configuration/security state: {SECRET_LOAD_ERROR}') from exc
