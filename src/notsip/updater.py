from __future__ import annotations
import hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
import httpx

class UpdateManager:
    def __init__(self,root:Path,settings,health_url='http://127.0.0.1:8765/api/health'):
        self.root=Path(root);self.settings=settings;self.health_url=health_url;self.dir=self.root/'updates';self.dir.mkdir(parents=True,exist_ok=True)
    @property
    def frozen(self):return bool(getattr(sys,'frozen',False))
    @property
    def current_exe(self):return Path(sys.executable).resolve() if self.frozen else None
    async def check(self):
        repo=getattr(self.settings,'github_repository','')
        if not repo:return {'available':False,'reason':'github_repository not configured'}
        headers={'Accept':'application/vnd.github+json'};token=os.getenv('NOTSIP_GITHUB_TOKEN','')
        if token:headers['Authorization']='Bearer '+token
        url=f'https://api.github.com/repos/{repo}/releases/latest'
        async with httpx.AsyncClient(timeout=20) as c:
            r=await c.get(url,headers=headers)
        if r.status_code==404:
            return {'available':False,'reason':'no published release'}
        if r.status_code in (401,403):
            return {'available':False,'reason':'GitHub release access denied','status_code':r.status_code}
        r.raise_for_status();d=r.json()
        return {'available':bool(d.get('tag_name')),'tag':d.get('tag_name'),'name':d.get('name'),'url':d.get('html_url'),'assets':[{'name':a['name'],'size':a['size'],'url':a['browser_download_url']} for a in d.get('assets',[])]}
    async def download(self,asset_url:str,sha256:str=''):
        token=os.getenv('NOTSIP_GITHUB_TOKEN','');headers={'Accept':'application/octet-stream'}
        if token:headers['Authorization']='Bearer '+token
        target=self.dir/f'update-{int(time.time())}.exe'
        async with httpx.AsyncClient(timeout=120,follow_redirects=True) as c:
            r=await c.get(asset_url,headers=headers);r.raise_for_status();target.write_bytes(r.content)
        digest=hashlib.sha256(target.read_bytes()).hexdigest()
        if sha256 and digest.lower()!=sha256.lower():target.unlink(missing_ok=True);raise ValueError('update SHA-256 verification failed')
        return {'status':'DOWNLOADED','path':str(target),'sha256':digest}
    def install_and_verify(self,new_exe:Path):
        if not self.frozen:raise RuntimeError('binary self-update is only available from a frozen installation')
        current=self.current_exe
        if not current.exists():raise FileNotFoundError(current)
        backup=self.dir/f'previous-{int(time.time())}.exe';shutil.copy2(current,backup)
        helper=self.dir/f'apply-{int(time.time())}.ps1'
        helper.write_text(f'''param()\n$ErrorActionPreference="Stop"\nStart-Sleep -Seconds 2\nCopy-Item -Force "{new_exe}" "{current}"\nStart-Process "{current}"\nStart-Sleep -Seconds 4\ntry {{ Invoke-WebRequest "{self.health_url}" -UseBasicParsing -TimeoutSec 5 | Out-Null }} catch {{ Copy-Item -Force "{backup}" "{current}"; Start-Process "{current}"; exit 2 }}\n''',encoding='utf-8')
        subprocess.Popen(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(helper)],creationflags=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0));return {'status':'STAGED','backup':str(backup),'restart_required':True}
