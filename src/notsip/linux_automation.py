from __future__ import annotations
import os,platform,shlex,subprocess,time
from pathlib import Path

class LinuxAutomation:
    """Local Linux execution surface; never elevates privileges and never shells through a user's login shell."""
    def __init__(self,workspace):self.workspace=Path(workspace).resolve()
    def _check(self):
        if platform.system()!='Linux':raise RuntimeError('Linux node required')
    def exec(self,command,timeout=60):
        self._check();text=str(command or '').strip()
        if not text:raise ValueError('command is required')
        if '\x00' in text:raise ValueError('NUL bytes are not allowed')
        timeout=max(1,min(int(timeout),180))
        env={k:v for k,v in os.environ.items() if k in {'PATH','HOME','LANG','LC_ALL','TERM','TMPDIR'}}
        started=time.time()
        p=subprocess.run(['/bin/bash','--noprofile','--norc','-c',text],cwd=str(self.workspace),env=env,capture_output=True,text=True,timeout=timeout)
        return {'status':'SUCCESS' if p.returncode==0 else 'FAILURE','returncode':p.returncode,'stdout':p.stdout[-20000:],'stderr':p.stderr[-20000:],'elapsed_sec':time.time()-started}
    def open_path(self,relative):
        self._check();p=(self.workspace/relative).resolve()
        if self.workspace not in p.parents and p!=self.workspace:raise PermissionError('path outside workspace')
        if not p.exists():raise FileNotFoundError(relative)
        subprocess.Popen(['xdg-open',str(p)],cwd=str(self.workspace),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);return {'status':'UNKNOWN','path':str(p.relative_to(self.workspace)),'verified':False,'note':'xdg-open launch requested; application state was not independently verified'}
