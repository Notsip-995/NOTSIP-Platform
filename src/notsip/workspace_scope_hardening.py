from __future__ import annotations
from pathlib import Path
from .actor_context import current_actor
from .actor_workspace import ActorWorkspace
from .execution_gate import ToolExecutionGate


def attach(app, registry, data_root):
    manager = ActorWorkspace(Path(data_root).resolve() / 'workspace')
    try:
        from .system_services import _search_workspace, _rename, _copy, _move, _delete, _archive
        from .connectors import Calendar
        from .app import settings, media
    except ImportError:
        return manager

    def workspace():
        return manager.for_actor(current_actor())

    def parse_calendar(path):
        return {'status':'SUCCESS','events':Calendar().parse(workspace().path(path))}

    def transcribe(path, language=''):
        raw=workspace().path(path).read_bytes()
        return media.transcribe(raw,'audio/webm',language or settings.stt_language)

    def perceive(path, prompt=''):
        raw=workspace().path(path).read_bytes()
        return media.perceive(raw,prompt or 'Describe visible evidence only.')

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
        'calendar_parse': parse_calendar,
        'voice_transcribe': transcribe,
        'perception_observe': perceive,
    }
    replaced=False
    for name, fn in wrappers.items():
        tool = registry.get(name)
        if tool is None:
            continue
        if getattr(tool,'_notsip_guarded',False):
            delattr(tool,'_notsip_guarded')
            if hasattr(tool,'_notsip_original_fn'):delattr(tool,'_notsip_original_fn')
        tool.fn=fn
        replaced=True
    if replaced:
        ToolExecutionGate.wrap_registry(registry)
    return manager
