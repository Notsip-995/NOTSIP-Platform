"""NOTSIP construction-directive compatibility alias.

ONE coherent runtime: ``python -m notsip`` -> ``notsip.core_runtime.app``
(authoritative instances in ``notsip.runtime_prod`` + ``notsip.app``).

``runtime_enterprise`` was a parallel full runtime graph (own FastAPI app and
own Store/Policy/Provider/Registry/Agent/World instances) sitting beside
``runtime_prod``. Per directive (retain/rewrite/move/split/merge/rename/wrap/
deprecate/delete toward ONE runtime; no parallel implementation), it is now a
thin alias to the canonical production graph. Nothing in the canonical boot
(``__main__``/``core_runtime``/``app``) or tests imports this module.
"""
from __future__ import annotations
from . import runtime_prod as _canonical
app = _canonical.app
store = _canonical.store
policy = _canonical.policy
registry = _canonical.registry
events = _canonical.events
provider = _canonical.provider
world = _canonical.world
jobs = _canonical.jobs
win = _canonical.win
uia = _canonical.uia
web = _canonical.web
browser = _canonical.browser
emailc = _canonical.emailc
calendarc = _canonical.calendarc
pairing = _canonical.pairing
agent = _canonical.agent
maint = _canonical.maint
media = _canonical.media
nodes = _canonical.nodes
recovery = _canonical.recovery
intellect = _canonical.intellect
auth = _canonical.auth
oauth = _canonical.oauth
require_auth = _canonical.require_auth
__all__ = ["app", "store", "policy", "registry", "events", "provider", "world", "jobs", "win", "uia", "web", "browser", "emailc", "calendarc", "pairing", "agent", "maint", "media", "nodes", "recovery", "intellect", "auth", "oauth", "require_auth"]