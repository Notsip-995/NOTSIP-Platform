from notsip.retrieval_router import RetrievalRouter
from notsip.external_adapters import RemoteComputeAdapter,RemoteSensingAdapter,HomeAdapter,BiometricTelemetryAdapter


def test_personal_commitment_query_is_private_first():
    p=RetrievalRouter().plan('What did I promise Sarah last week?')
    assert p.public_web is False
    assert p.sources[0] in {'personal_memory','conversations','email','calendar','documents'}
    assert 'web' not in p.sources or p.sources[-1] == 'web'


def test_server_diagnostic_query_prioritizes_system_sources():
    p=RetrievalRouter().plan('Why is my server slow?')
    assert 'system_telemetry' in p.sources
    assert 'system_logs' in p.sources


def test_remote_adapters_fail_closed_without_https_endpoint():
    assert RemoteComputeAdapter('http://example.com','token').configured is False
    assert RemoteSensingAdapter('http://example.com','token').configured is False
    assert HomeAdapter('http://example.com','token').configured is False
    assert BiometricTelemetryAdapter('http://example.com','token').configured is False
