from __future__ import annotations
from pathlib import Path
from .actor_context import current_actor
from .actor_workspace import ActorWorkspace


def attach(app, registry, data_root):
    manager = ActorWorkspace(Path(data_root).resolve() / 'workspace')
    try:
        from .system_services import _search_workspace, _rename, _copy, _move, _delete, _archive
    except ImportError:
        return manager

    def workspace():
        return manager.for_actor(current_actor())

    wrappers = {
        'list_files': lambda query='': {'status':'SUCCESS','files':workspace().list(query)},
        'read_file': lambda path: {'status':'SUCCESS','content':workspace().read(path)},
        'write_file': lambda path, content: {'status':'SUCCESS','path':workspace().write(path,content)},
        'search_workspace': lambda query, limit=25: _search_workspace(workspace(),query,limit),
        'file_rename': lambda source,target: _rename(workspace(),source,target),
        'file_copy': lambda source,target: _copy(workspace(),source,target),
        'file_move': lambda source,target: _move(workspace(),source,target),
        'file_delete': lambda path: _delete(workspace(),path),
        'file_archive': lambda paths,archive: _archive(workspace(),paths,archive),
    }
    for name, fn in wrappers.items():
        tool = registry.get(name)
        if tool is not None:
            tool.fn = fn
    return manager
