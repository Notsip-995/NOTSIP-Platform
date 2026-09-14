import asyncio


def _call_degraded():
    import notsip.runtime_prod as rp
    return asyncio.run(rp.degraded(None))


def test_degraded_reports_restart_pending_when_persisted_differs(tmp_path):
    import notsip.app as mod
    original_dir = mod.settings.data_dir
    original_store = mod.config_store
    mod.settings.data_dir = str(tmp_path)
    mod.config_store = mod.ConfigStore(tmp_path)

    mod.settings.llm_base_url = 'https://runtime.example/v1'
    mod.settings.llm_model = 'runtime-model'
    mod.config_store.save({'llm_base_url': 'https://persisted.example/v1', 'llm_model': 'persisted-model'})

    try:
        result = _call_degraded()
        assert 'llm_base_url' in result['restart_pending']
        assert 'llm_model' in result['restart_pending']
    finally:
        mod.settings.data_dir = original_dir
        mod.config_store = original_store


def test_degraded_no_restart_pending_when_matching(tmp_path):
    import notsip.app as mod
    original_dir = mod.settings.data_dir
    original_store = mod.config_store
    mod.settings.data_dir = str(tmp_path)
    mod.config_store = mod.ConfigStore(tmp_path)
    mod.settings.llm_base_url = 'https://same.example/v1'
    mod.settings.llm_model = 'same-model'
    mod.config_store.save({'llm_base_url': 'https://same.example/v1', 'llm_model': 'same-model'})

    try:
        result = _call_degraded()
        assert 'llm_base_url' not in result['restart_pending']
        assert 'llm_model' not in result['restart_pending']
    finally:
        mod.settings.data_dir = original_dir
        mod.config_store = original_store