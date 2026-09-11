import asyncio
from types import SimpleNamespace
from notsip.external_adapters import AdapterUnavailable, HomeAdapter, BiometricTelemetryAdapter, attach
from notsip.policy import Risk
from notsip.tools import Registry


def test_home_and_biometric_tools_register_with_expected_risk():
    registry=Registry();settings=SimpleNamespace(home_adapter_url='',home_adapter_token='',biometric_adapter_url='',biometric_adapter_token='')
    attach(registry,settings)
    assert registry.get('home_command') is not None
    assert registry.get('home_command').risk==Risk.HIGH
    assert registry.get('biometric_latest') is not None
    assert registry.get('biometric_latest').risk==Risk.MEDIUM


def test_unconfigured_home_and_biometric_adapters_do_not_fabricate_success():
    home=HomeAdapter('','');bio=BiometricTelemetryAdapter('','')
    async def run():
        for coro in (home.command('lamp','on'),bio.latest()):
            try:
                await coro
            except AdapterUnavailable:
                continue
            raise AssertionError('unconfigured adapter unexpectedly returned success')
    asyncio.run(run())
