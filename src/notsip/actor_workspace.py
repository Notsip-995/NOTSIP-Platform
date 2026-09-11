from __future__ import annotations
import hashlib
from pathlib import Path
from .actor_context import current_actor
from .tools import Workspace


class ActorWorkspace:
    """Expose an isolated workspace root per authenticated actor."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def for_actor(self, actor: str | None = None) -> Workspace:
        actor = str(actor or current_actor()).strip() or 'primary-user'
        if actor == 'primary-user':
            path = self.root
        else:
            digest = hashlib.sha256(actor.encode('utf-8')).hexdigest()[:24]
            path = self.root / 'actors' / digest
        path.mkdir(parents=True, exist_ok=True)
        return Workspace(path)
