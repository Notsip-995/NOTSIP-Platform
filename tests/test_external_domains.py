import asyncio
from types import SimpleNamespace
from notsip.external_domains import ExternalDomainAdapter,_public_https,attach
from notsip.policy import Risk
from notsip.tools import Registry


def test_missing_flight_endpoint_is_explicitly_blocked():
    adapter=ExternalDomainAdapter(SimpleNamespace(flight_planning_url='',flight_planning_token=''))
    result=asyncio.run(adapter.flight_plan('KGL','JFK'))
    assert result['status']=='BLOCKED_BY_EXTERNAL_ENVIRONMENT'


def test_private_external_endpoint_is_rejected(monkeypatch):
    monkeypatch.setattr('notsip.external_domains.socket.getaddrinfo',lambda *a,**k:[(2,1,6,'',('127.0.0.1',443))])
    try:_public_https('https://example.invalid/api')
    except ValueError as exc:assert 'non-public' in str(exc)
    else:raise AssertionError('private endpoint was accepted')


def test_external_tools_are_registered_with_risk():
    settings=SimpleNamespace(flight_planning_url='',flight_planning_token='',remote_sensing_url='',remote_sensing_token='',remote_compute_url='',remote_compute_token='')
    registry=Registry();attach(registry,settings)
    assert registry.get('flight_plan').risk==Risk.MEDIUM
    assert registry.get('remote_sensing_query').risk==Risk.MEDIUM
    assert registry.get('remote_compute_execute').risk==Risk.HIGH
    assert registry.get('remote_compute_execute').destructive is True
