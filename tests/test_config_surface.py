import json
import pytest
from pathlib import Path
from notsip.config import Settings
from notsip.product_layer import ConfigStore


def test_settings_include_required_external_adapter_and_capability_fields():
    fields=Settings.model_fields
    for name in ('remote_compute_url','remote_sensing_url','home_adapter_url','biometric_adapter_url','windows_publisher_thumbprint','capability_levels'):
        assert name in fields


def test_config_public_surface_redacts_adapter_tokens(tmp_path):
    c=ConfigStore(tmp_path)
    c.save({'remote_compute_url':'https://compute.example','remote_compute_token':'super-secret','capability_levels':{'WRITE_CALENDAR':2}})
    raw=json.loads((Path(tmp_path)/'config.json').read_text())
    assert raw['settings']['remote_compute_url']=='https://compute.example'
    assert 'remote_compute_token' not in raw['settings']
    assert raw['settings']['capability_levels']['WRITE_CALENDAR']==2


def test_remote_api_key_binding_fails_closed_without_key(tmp_path):
    s=Settings(host='0.0.0.0',data_dir=str(tmp_path),auth_mode='api_key',api_key='')
    with pytest.raises(RuntimeError,match='Remote binding requires'):
        s.ensure()


def test_remote_oidc_binding_fails_closed_without_provider_configuration(tmp_path):
    s=Settings(host='0.0.0.0',data_dir=str(tmp_path),auth_mode='oidc',oidc_issuer='',oidc_client_id='',oidc_redirect_uri='')
    with pytest.raises(RuntimeError,match='Remote binding with OIDC requires'):
        s.ensure()
