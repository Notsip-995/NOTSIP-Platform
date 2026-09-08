from pathlib import Path


def test_oidc_session_guard_exists_before_actor_context_processing():
    runtime=Path('src/notsip/core_runtime.py').read_text(encoding='utf-8')
    guard=Path('src/notsip/oidc_session_guard.py').read_text(encoding='utf-8')
    assert 'attach_oidc_session_guard(app,auth)' in runtime
    assert "headers.append((b'authorization', b'Bearer oidc-session'))" in guard
    assert "auth.mode == 'oidc'" in guard
