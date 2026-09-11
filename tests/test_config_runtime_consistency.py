from pathlib import Path
import json


def test_non_bootstrap_config_update_is_deferred(monkeypatch,tmp_path):
    import notsip.app as mod
    original=mod.settings.llm_base_url
    mod.settings.data_dir=str(tmp_path)
    mod.config_store=mod.ConfigStore(tmp_path)
    mod.config_store.save({'llm_base_url': original})
    requested={'llm_base_url':'https://new.example/v1','llm_model':'model-b'}
    result=mod._apply_config(requested,bootstrap=False)
    assert result['status']=='SUCCESS'
    assert result['restart_required'] is True
    assert result['applied_to_runtime'] is False
    assert mod.settings.llm_base_url==original
    persisted=mod.config_store.load()['settings']
    assert persisted['llm_base_url']==requested['llm_base_url']
    assert persisted['llm_model']==requested['llm_model']


def test_bootstrap_config_update_is_applied(monkeypatch,tmp_path):
    import notsip.app as mod
    mod.settings.data_dir=str(tmp_path)
    mod.config_store=mod.ConfigStore(tmp_path)
    mod.settings.llm_base_url=''
    result=mod._apply_config({'llm_base_url':'https://bootstrap.example/v1'},bootstrap=True)
    assert result['status']=='SUCCESS'
    assert result['applied_to_runtime'] is True
    assert mod.settings.llm_base_url=='https://bootstrap.example/v1'


def test_deferred_secret_never_enters_plaintext_config(monkeypatch,tmp_path):
    import notsip.app as mod
    mod.settings.data_dir=str(tmp_path)
    mod.config_store=mod.ConfigStore(tmp_path)
    mod._apply_config({'llm_api_key':'top-secret-value'},bootstrap=False)
    data=json.loads(Path(tmp_path,'config.json').read_text())
    assert 'llm_api_key' not in data.get('settings',{})
    assert mod.auth.secrets.get('NOTSIP_LLM_API_KEY')=='top-secret-value'
