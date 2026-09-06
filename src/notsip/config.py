from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
class Settings(BaseSettings):
    host:str='127.0.0.1'; port:int=8765; data_dir:str='./data'; local_timezone:str='Africa/Kigali'; max_tool_rounds:int=8; autonomy_level:int=2
    llm_base_url:str=''; llm_api_key:str=''; llm_model:str=''; brave_api_key:str=''; api_key:str=''; event_hmac_secret:str=''; pairing_secret:str=''
    model_config=SettingsConfigDict(env_prefix='NOTSIP_',env_file='.env',extra='ignore')
    def ensure(self): Path(self.data_dir).mkdir(parents=True,exist_ok=True); (Path(self.data_dir)/'workspace').mkdir(parents=True,exist_ok=True)
settings=Settings(); settings.ensure()
