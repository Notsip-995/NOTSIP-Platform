from __future__ import annotations
import hashlib, json, os, subprocess, sys, time
from pathlib import Path
from .config import settings as runtime_settings

class SelfMaintenance:
    def __init__(self, repo_root: Path):
        self.root = repo_root.resolve()

    @property
    def frozen(self):
        return bool(getattr(sys, 'frozen', False))

    inventory = lambda self: sorted([
        {'path':str(p.relative_to(self.root)).replace('\\','/'),'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in self.root.rglob('*') if p.is_file() and not any(part in {'.git','.venv','__pycache__','.pytest_cache','data','build','dist'} for part in p.relative_to(self.root).parts)
    ], key=lambda x:x['path'])

    def read(self, path):
        p=(self.root/path).resolve()
        if self.root not in p.parents and p!=self.root: raise PermissionError('path outside NOTSIP source workspace')
        return p.read_text(encoding='utf-8')

    def git(self,*args):
        p=subprocess.run(['git',*args],cwd=self.root,capture_output=True,text=True,timeout=60)
        return {'returncode':p.returncode,'stdout':p.stdout[-20000:],'stderr':p.stderr[-20000:]}

    def verify(self):
        if self.frozen:
            import py_compile
            failures=[]
            for p in self.root.rglob('*.py'):
                if any(part in {'.git','__pycache__','data','build','dist'} for part in p.parts): continue
                try: py_compile.compile(str(p),doraise=True)
                except Exception as exc: failures.append({'path':str(p.relative_to(self.root)),'error':str(exc)})
            return {'compile_ok':not failures,'compile_failures':failures,'tests_ok':None,'tests_unavailable':True,'git':self.git('status','--short') if (self.root/'.git').exists() else {'returncode':0,'stdout':'','stderr':'source workspace is not a git checkout'}}
        compile_run=subprocess.run([os.sys.executable,'-m','compileall','-q','src'],cwd=self.root,capture_output=True,text=True,timeout=120)
        test_run=subprocess.run([os.sys.executable,'-m','pytest','-q'],cwd=self.root,capture_output=True,text=True,timeout=180)
        return {'compile_ok':compile_run.returncode==0,'compile_stdout':compile_run.stdout[-10000:],'compile_stderr':compile_run.stderr[-10000:],'tests_ok':test_run.returncode==0,'tests_stdout':test_run.stdout[-20000:],'tests_stderr':test_run.stderr[-20000:],'git':self.git('status','--short')}

    def _safe_patch(self, patch_text):
        lowered=patch_text.lower()
        if 'password' in lowered or 'begin private key' in lowered or 'sk-' in lowered or 'api_key=' in lowered:
            raise ValueError('refusing patch containing likely secrets')

    def apply_patch(self, patch_text, confirmation):
        enabled = bool(getattr(runtime_settings,'self_modify_enabled',False))
        env_override = os.getenv('NOTSIP_SELF_MODIFY_ENABLED','').lower() in {'1','true','yes'}
        if confirmation != 'APPLY_SELF_CHANGE': raise PermissionError('explicit confirmation required')
        if not enabled and not env_override: raise PermissionError('self-modification is disabled')
        self._safe_patch(patch_text)
        if self.frozen and not (self.root/'.git').exists():
            raise RuntimeError('installed self-maintenance requires a durable source checkout; source workspace is read/verify capable but binary replacement must use the signed updater')
        branch=f'notsip/self-fix-{int(time.time())}'
        original=self.git('rev-parse','--abbrev-ref','HEAD')['stdout'].strip()
        if not original or not self.git('status','--porcelain')['returncode']==0: raise RuntimeError('unable to inspect source repository')
        created=self.git('switch','-c',branch)
        if created['returncode']!=0: raise RuntimeError(created['stderr'])
        try:
            check=subprocess.run(['git','apply','--check','-'],cwd=self.root,input=patch_text,text=True,capture_output=True,timeout=60)
            if check.returncode!=0: raise RuntimeError(check.stderr[-10000:])
            applied=subprocess.run(['git','apply','-'],cwd=self.root,input=patch_text,text=True,capture_output=True,timeout=60)
            if applied.returncode!=0: raise RuntimeError(applied.stderr[-10000:])
            verification=self.verify()
            if not verification['compile_ok'] or verification.get('tests_ok') is False:
                self.git('reset','--hard','HEAD');self.git('switch',original);return {'status':'ROLLED_BACK','branch':branch,'verification':verification}
            added=self.git('add','-A')
            if added['returncode']!=0: raise RuntimeError(added['stderr'])
            committed=self.git('commit','-m','NOTSIP self-maintenance: verified change')
            if committed['returncode']!=0: raise RuntimeError(committed['stderr'])
            sha=self.git('rev-parse','HEAD')['stdout'].strip();self.git('switch',original)
            return {'status':'COMMITTED','branch':branch,'commit':sha,'verification':verification}
        except Exception:
            self.git('reset','--hard','HEAD');self.git('switch',original);raise
