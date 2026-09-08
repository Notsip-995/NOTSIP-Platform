from __future__ import annotations
import hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path
from urllib.parse import urlparse
import httpx
from . import __version__

class UpdateManager:
    def __init__(self,root:Path,settings,health_url=''):
        self.root=Path(root);self.settings=settings;self.health_url=health_url or f'http://{settings.host}:{settings.port}/api/health';self.dir=self.root/'updates';self.dir.mkdir(parents=True,exist_ok=True)
    @property
    def frozen(self):return bool(getattr(sys,'frozen',False))
    @property
    def current_exe(self):return Path(sys.executable).resolve() if self.frozen else None
    def _trusted_asset(self,url:str)->bool:
        p=urlparse(url);repo=str(getattr(self.settings,'github_repository','')).strip('/ ')
        return p.scheme=='https' and p.netloc.lower()=='github.com' and repo and p.path.startswith(f'/{repo}/releases/download/') and p.path.lower().endswith('.exe')
    @staticmethod
    def _version_tuple(value:str):
        raw=str(value or '').strip().lower().lstrip('v');parts=raw.split('.')
        if len(parts)<2 or len(parts)>4 or any(not p.isdigit() for p in parts):return None
        nums=[int(p) for p in parts];nums.extend([0]*(4-len(nums)));return tuple(nums)
    async def check(self):
        repo=getattr(self.settings,'github_repository','')
        if not repo:return {'available':False,'reason':'github_repository not configured'}
        headers={'Accept':'application/vnd.github+json'};token=os.getenv('NOTSIP_GITHUB_TOKEN','')
        if token:headers['Authorization']='Bearer '+token
        url=f'https://api.github.com/repos/{repo}/releases/latest'
        async with httpx.AsyncClient(timeout=20) as c:r=await c.get(url,headers=headers)
        if r.status_code==404:return {'available':False,'reason':'no published release'}
        if r.status_code in (401,403):return {'available':False,'reason':'GitHub release access denied','status_code':r.status_code}
        r.raise_for_status();d=r.json();tag=d.get('tag_name','');current=self._version_tuple(__version__);latest=self._version_tuple(tag)
        if not current or not latest:return {'available':False,'reason':'release version is not semantic','tag':tag}
        assets=[]
        release_assets=d.get('assets',[])
        by_name={str(a.get('name','')):a for a in release_assets}
        for a in release_assets:
            name=str(a.get('name',''))
            if not name.lower().endswith('.exe'):continue
            sha_asset=by_name.get(name+'.sha256')
            assets.append({'name':name,'size':a['size'],'url':a['browser_download_url'],'sha256_url':sha_asset.get('browser_download_url') if sha_asset else None,'publisher_thumbprint_required':bool(getattr(self.settings,'windows_publisher_thumbprint',''))})
        return {'available':latest>current,'current_version':__version__,'tag':tag,'name':d.get('name'),'url':d.get('html_url'),'assets':assets}
    async def download(self,asset_url:str,sha256:str=''):
        if not self._trusted_asset(asset_url):raise ValueError('update asset is not from the configured GitHub release path or is not an EXE')
        if not sha256 or len(sha256.strip())!=64:raise ValueError('update SHA-256 is required')
        token=os.getenv('NOTSIP_GITHUB_TOKEN','');headers={'Accept':'application/octet-stream'}
        if token:headers['Authorization']='Bearer '+token
        target=self.dir/f'update-{int(time.time())}.exe'
        async with httpx.AsyncClient(timeout=120,follow_redirects=True) as c:r=await c.get(asset_url,headers=headers);r.raise_for_status();target.write_bytes(r.content)
        digest=hashlib.sha256(target.read_bytes()).hexdigest()
        if digest.lower()!=sha256.lower():target.unlink(missing_ok=True);raise ValueError('update SHA-256 verification failed')
        return {'status':'DOWNLOADED','path':str(target),'sha256':digest}
    @staticmethod
    def _powershell_quote(value):return "'"+str(value).replace("'","''")+"'"
    def _verify_authenticode(self,new_exe:Path):
        thumbprint=str(getattr(self.settings,'windows_publisher_thumbprint','')).replace(' ','').upper()
        if os.name!='nt':return {'status':'BLOCKED_BY_EXTERNAL_ENVIRONMENT','reason':'Windows Authenticode verification requires Windows'}
        if not thumbprint:return {'status':'BLOCKED_BY_EXTERNAL_ENVIRONMENT','reason':'windows_publisher_thumbprint is not configured'}
        command="$s=Get-AuthenticodeSignature -FilePath $args[0]; [pscustomobject]@{Status=[string]$s.Status;Thumbprint=[string]$s.SignerCertificate.Thumbprint;Subject=[string]$s.SignerCertificate.Subject}|ConvertTo-Json -Compress"
        r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command,'--',str(new_exe)],capture_output=True,text=True,timeout=15)
        if r.returncode!=0:raise RuntimeError('Authenticode verification command failed: '+r.stderr[-2000:])
        try:data=json.loads(r.stdout)
        except json.JSONDecodeError as exc:raise RuntimeError('Authenticode verification returned invalid data') from exc
        actual=str(data.get('Thumbprint','')).replace(' ','').upper();status=str(data.get('Status',''))
        if status!='Valid' or actual!=thumbprint:raise RuntimeError(f'Authenticode verification failed: status={status!r}, thumbprint={actual!r}')
        return {'status':'VALID','thumbprint':actual,'subject':data.get('Subject','')}
    def install_and_verify(self,new_exe:Path):
        if not self.frozen:raise RuntimeError('binary self-update is only available from a frozen installation')
        current=self.current_exe
        if not current.exists():raise FileNotFoundError(current)
        signer=self._verify_authenticode(new_exe)
        if signer.get('status')!='VALID':raise RuntimeError(signer.get('reason','publisher verification unavailable'))
        backup=self.dir/f'previous-{int(time.time())}.exe';shutil.copy2(current,backup)
        helper=self.dir/f'apply-{int(time.time())}.ps1'
        new_s=self._powershell_quote(new_exe);cur_s=self._powershell_quote(current);backup_s=self._powershell_quote(backup);health_s=self._powershell_quote(self.health_url)
        helper.write_text(f'''param()\n$ErrorActionPreference="Stop"\nStart-Sleep -Seconds 2\nCopy-Item -Force {new_s} {cur_s}\nStart-Process {cur_s}\nStart-Sleep -Seconds 4\ntry {{ $r=Invoke-WebRequest {health_s} -UseBasicParsing -TimeoutSec 5; if($r.StatusCode -ne 200){{ throw "health check returned HTTP $($r.StatusCode)" }} }} catch {{ Copy-Item -Force {backup_s} {cur_s}; Start-Process {cur_s}; exit 2 }}\n''',encoding='utf-8')
        subprocess.Popen(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(helper)],creationflags=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0));return {'status':'STAGED','backup':str(backup),'restart_required':True,'publisher':signer}
