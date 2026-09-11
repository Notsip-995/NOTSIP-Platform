"""Compatibility facade for the single authoritative NOTSIP runtime.

The production runtime is assembled once by ``notsip.core_runtime``.  This
module intentionally re-exports those live instances so legacy imports cannot
create a second Store/Policy/Agent graph with divergent state.
"""
from .core_runtime import *  # noqa: F401,F403
