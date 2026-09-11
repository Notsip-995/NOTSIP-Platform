from types import SimpleNamespace
from notsip.setup_readiness import _configured


def test_configured_treats_blank_and_whitespace_as_missing():
    assert not _configured('')
    assert not _configured('   ')
    assert _configured('https://example.test')


def test_required_reasoning_provider_needs_complete_endpoint_model_and_key():
    s=SimpleNamespace(llm_base_url='https://example.test',llm_model='model',llm_api_key='key',fallback_llm_base_url='',fallback_llm_model='',fallback_llm_api_key='')
    assert _configured(s.llm_base_url) and _configured(s.llm_model) and _configured(s.llm_api_key)
