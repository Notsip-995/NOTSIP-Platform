from __future__ import annotations
import py_compile
import subprocess
import sys
from pathlib import Path


def attach(maintenance):
    def verify():
        root=Path(maintenance.root).resolve()
        if getattr(sys,'frozen',False):
            failures=[]
            for path in root.rglob('*.py'):
                if any(part in {'.git','.venv','__pycache__','.pytest_cache','data','dist','build','backups'} for part in path.relative_to(root).parts):
                    continue
                try:
                    py_compile.compile(str(path),doraise=True)
                except Exception as exc:
                    failures.append({'path':str(path.relative_to(root)),'error':str(exc)})
            return {
                'compile_ok':not failures,
                'compile_failures':failures,
                'tests_ok':None,
                'tests_unavailable':True,
                'reason':'installed frozen runtime cannot execute its own pytest suite; source tree compile verification completed',
            }
        compile_run=subprocess.run([sys.executable,'-m','compileall','-q','src'],cwd=root,capture_output=True,text=True,timeout=180)
        test_run=subprocess.run([sys.executable,'-m','pytest','-q'],cwd=root,capture_output=True,text=True,timeout=300)
        return {
            'compile_ok':compile_run.returncode==0,
            'tests_ok':test_run.returncode==0,
            'compile_stderr':compile_run.stderr[-4000:],
            'tests_stdout':test_run.stdout[-8000:],
            'tests_stderr':test_run.stderr[-8000:],
        }
    maintenance.verify=verify
    return maintenance
