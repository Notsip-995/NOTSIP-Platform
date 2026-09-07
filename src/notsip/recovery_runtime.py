"""Compatibility hook for older Store implementations.

Current SQLite and PostgreSQL stores implement restore_runtime_state natively.
This module must never replace those canonical implementations at runtime.
"""

def attach(store):
    if hasattr(store, 'restore_runtime_state'):
        return store
    raise RuntimeError('Store must implement restore_runtime_state')
