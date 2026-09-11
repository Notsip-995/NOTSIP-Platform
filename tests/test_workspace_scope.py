from pathlib import Path
import pytest


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


def test_scoped_workspace_replacements_are_reguarded_after_registry_mutation():
    text=Path('src/notsip/workspace_scope_hardening.py').read_text(encoding='utf-8')
    assert 'from .execution_gate import ToolExecutionGate' in text
    assert 'delattr(tool,\'_notsip_guarded\')' in text
    assert 'ToolExecutionGate.wrap_registry(registry)' in text
