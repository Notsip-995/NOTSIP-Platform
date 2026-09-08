from pathlib import Path


def test_actor_workspace_roots_are_isolated(tmp_path):
    from notsip.actor_workspace import ActorWorkspace
    manager = ActorWorkspace(Path(tmp_path) / 'workspace')
    a = manager.for_actor('actor-a')
    b = manager.for_actor('actor-b')
    a.write('private.txt', 'A')
    assert a.read('private.txt') == 'A'
    assert b.list() == []
    assert a.root != b.root


def test_primary_actor_keeps_legacy_workspace_root(tmp_path):
    from notsip.actor_workspace import ActorWorkspace
    manager = ActorWorkspace(Path(tmp_path) / 'workspace')
    primary = manager.for_actor('primary-user')
    assert primary.root == (Path(tmp_path) / 'workspace').resolve()
