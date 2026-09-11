from __future__ import annotations
import json,os,time
from pathlib import Path
from .product_layer import ProcessGuard

class LauncherProcessGuard(ProcessGuard):
    """Process lock that never deletes an unreadable lock file automatically."""
    def acquire(self):
        try:
            fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
            with os.fdopen(fd,'w',encoding='utf-8') as stream:
                json.dump({'pid':os.getpid(),'created':time.time(),'host':__import__('socket').gethostname()},stream)
            self._owned=True
            return True
        except FileExistsError:
            try:
                info=json.loads(self.path.read_text(encoding='utf-8'))
                pid=int(info.get('pid',0))
            except (OSError,ValueError,TypeError,json.JSONDecodeError) as exc:
                raise RuntimeError('NOTSIP instance lock is corrupt; refusing to remove it automatically') from exc
            if pid<=0:
                raise RuntimeError('NOTSIP instance lock has no valid process id; refusing to remove it automatically')
            if self._pid_alive(pid):
                return False
            try:
                self.path.unlink()
            except FileNotFoundError:
                return self.acquire()
            except OSError as exc:
                raise RuntimeError(f'cannot remove stale NOTSIP instance lock: {exc}') from exc
            return self.acquire()
