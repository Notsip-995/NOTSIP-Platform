from notsip.actor_context import set_actor, reset_actor
import pytest
from notsip.product_routes import _require_primary


def test_control_plane_guard_rejects_secondary_actor():
    token=set_actor('oidc:secondary')
    try:
        with pytest.raises(Exception):
            _require_primary()
    finally:
        reset_actor(token)


def test_control_plane_guard_accepts_primary_actor():
    token=set_actor('primary-user')
    try:
        assert _require_primary() is None
    finally:
        reset_actor(token)
