import asyncio
from types import SimpleNamespace
from notsip.browser_hardening import attach
from notsip.policy import Risk
from notsip.tools import Registry


def test_browser_interaction_limit_is_enforced():
    registry=Registry()
    attach(type('App',(),{'router':type('R',(),{'routes':[]})()})(),lambda *_a,**_k:None,None,SimpleNamespace(),registry)
    tool=registry.get('browser_interact')
    try:asyncio.run(tool.fn('https://example.com',[{'type':'click','selector':'#x'}]*26))
    except ValueError as exc:assert '25 actions' in str(exc)
    else:raise AssertionError('browser workflow limit was not enforced')


def test_browser_interaction_is_high_risk():
    registry=Registry();attach(type('App',(),{'router':type('R',(),{'routes':[]})()})(),lambda *_a,**_k:None,None,SimpleNamespace(),registry)
    tool=registry.get('browser_interact');assert tool.risk==Risk.HIGH and tool.destructive is True
