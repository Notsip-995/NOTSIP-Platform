from __future__ import annotations
import hashlib, json, os, subprocess, time
from pathlib import Path

class SelfMaintenance:
    def __init__(self, repo_root: Path):
        self.root = repo_root.resolve()

    def inventory(self):
        files=[]
        for p in self.root.rglob('*'):
            if not p.is_file(): continue
            rel=p.relative_to(self.root)
            if any(part in {'.git','.venv','__pycache__','.pytest_cache','data','build','dist'} for part in rel.parts): continue
            files.append({'path':str(rel).replace('\\','/'),'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        return sorted(files,key=lambda x:x['path'])

    def read(self, path):
        p=(self.root/path).resolve()
        if self.root not in p.parents and p!=self.root: raise PermissionError('path outside repository')
        return p.read_text(encoding='utf-8')

    def git(self,*args):
        p=subprocess.run(['git',*args],cwd=self.root,capture_output=True,text=True,timeout=60)
        return {'returncode':p.returncode,'stdout':p.stdout[-20000:],'stderr':p.stderr[-20000:]}

    def verify(self):
        compile_run=subprocess.run([os.sys.executable,'-m','compileall','-q','src'],cwd=self.root,capture_output=True,text=True,timeout=120)
        test_run=subprocess.run([os.sys.executable,'-m','pytest','-q'],cwd=self.root,capture_output=True,text=True,timeout=180)
        return {'compile_ok':compile_run.returncode==0,'compile_stdout':compile_run.stdout[-10000:],'compile_stderr':compile_run.stderr[-10000:],'tests_ok':test_run.returncode==0,'tests_stdout':test_run.stdout[-20000:],'tests_stderr':test_run.stderr[-20000:],'git':self.git('status','--short')}

    def apply_patch(self, patch_text, confirmation):
        if confirmation != 'APPLY_SELF_CHANGE':
            raise PermissionError('explicit confirmation required')
        if os.getenv('NOTSIP_SELF_MODIFY_ENABLED','false').lower() not in {'1','true','yes'}:
            raise PermissionError('self-modification is disabled')
        if 'password' in patch_text.lower() or 'BEGIN PRIVATE KEY' in patch_text or 'sk-' in patch_text:
            raise ValueError('refusing patch containing likely secrets')
        branch=f'notsip/self-fix-{int(time.time())}'
        original=self.git('rev-parse','--abbrev-ref','HEAD')['stdout'].strip()
        created=self.git('switch','-c',branch)
        if created['returncode']!=0: raise RuntimeError(created['stderr'])
        try:
            check=subprocess.run(['git','apply','--check','-'],cwd=self.root,input=patch_text,text=True,capture_output=True,timeout=60)
            if check.returncode!=0: raise RuntimeError(check.stderr[-10000:])
            apply=subprocess.run(['git','apply','-'],cwd=self.root,input=patch_text,text=True,capture_output=True,timeout=60)
            if apply.returncode!=0: raise RuntimeError(apply.stderr[-10000:])
            verification=self.verify()
            if not verification['compile_ok'] or not verification['tests_ok']:
                self.git('reset','--hard','HEAD')
                self.git('switch',original)
                return {'status':'ROLLED_BACK','branch':branch,'verification':verification}
            commit=self.git('add','-A')
            if commit['returncode']==0: commit=self.git('commit','-m','NOTSIP self-maintenance: verified change')
            sha=self.git('rev-parse','HEAD')['stdout'].strip()
            self.git('switch',original)
            return {'status':'COMMITTED','branch':branch,'commit':sha,'verification':verification}
        except Exception:
            self.git('reset','--hard','HEAD')
            self.git('switch',original)
            raise
