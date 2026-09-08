from __future__ import annotations
import hashlib,json,os,re,shutil,subprocess,sys,time,uuid
from pathlib import Path
from urllib.parse import urljoin,urlparse
import httpx
from . import __version__

class UpdateManager:
    def __init__(self,root:Path,settings,health_url=''):
        self.root=Path(root);self.settings=settings;self.health_url=health_url or f'http://127.0.0.1:{settings.port}/healthz';self.dir=(self.root/'updates').resolve();self.dir.mkdir(parents=True,exist_ok=True)
    @property
    def frozen(self):return bool(getattr(sys,'frozen',False))
    @property
    def current_exe(self):return Path(sys.executable).resolve() if self.frozen else None
    def _trusted_asset(self,url:str)->bool:
        p=urlparse(url);repo=str(getattr(self.settings,'github_repository','')).strip('/ ');return p.scheme=='https' and p.netloc.lower()=='github.com' and repo and p.path.startswith(f'/{repo}/releases/download/') and p.path.lower().endswith('.exe')
    @staticmethod
    def _trusted_redirect(url:str)->bool:
        p=urlparse(str(url));host=(p.hostname or '').lower();return p.scheme=='https' and host in {'github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'}
    def _trusted_manifest(self,url:str)->bool:
        p=urlparse(url);repo=str(getattr(self.settings,'github_repository','')).strip('/ ');return p.scheme=='https' and p.netloc.lower()=='github.com' and repo and p.path.startswith(f'/{repo}/releases/download/') and p.path.lower().endswith('.sha256')
    def _managed_update_path(self,new_exe:Path)->Path:
        path=Path(new_exe).resolve()
        try:path.relative_to(self.dir)
        except ValueError:raise ValueError('self-update executable must reside in the managed updates directory') from None
        if path.suffix.lower()!='.exe':raise ValueError('self-update executable must be an EXE')
        if not path.is_file():raise FileNotFoundError(path)
        return path
    @staticmethod
    def _version_tuple(value:str):
        raw=str(value or '').strip().lower().lstrip('v');parts=raw.split('.')
        if len(parts)<2 or len(parts)>4 or any(not p.isdigit() for p in parts):return None
        nums=[int(p) for p in parts];nums.extend([0]*(4-len(parts)));return tuple(nums)
    async def check(self):
        repo=getattr(self.settings,'github_repository','')
        if not repo:return {'available':False,'reason':'github_repository not configured'}
        headers={'Accept':'application/vnd.github+json'};token=os.getenv('NOTSIP_GITHUB_TOKEN','')
        if token:headers['Authorization']='Bearer '+token
        async with httpx.AsyncClient(timeout=20) as c:r=await c.get(f'https://api.github.com/repos/{repo}/releases/latest',headers=headers)
        if r.status_code==404:return {'available':False,'reason':'no published release'}
        if r.status_code in (401,403):return {'available':False,'reason':'GitHub release access denied','status_code':r.status_code}
        r.raise_for_status();d=r.json();tag=d.get('tag_name','');current=self._version_tuple(__version__);latest=self._version_tuple(tag)
        if not current or not latest:return {'available':False,'reason':'release version is not semantic','tag':tag}
        assets=[];release_assets=d.get('assets',[]);by_name={str(a.get('name','')):a for a in release_assets}
        for a in release_assets:
            name=str(a.get('name',''))
            if not name.lower().endswith('.exe'):continue
            sha_asset=by_name.get(name+'.sha256');assets.append({'name':name,'size':a['size'],'url':a['browser_download_url'],'sha256_url':sha_asset.get('browser_download_url') if sha_asset else None,'publisher_thumbprint_required':bool(getattr(self.settings,'windows_publisher_thumbprint',''))})
        return {'available':latest>current,'current_version':__version__,'tag':tag,'name':d.get('name'),'url':d.get('html_url'),'assets':assets}
    async def _fetch_manifest_sha(self,url:str,expected_name:str):
        if not self._trusted_manifest(url):raise ValueError('update SHA-256 manifest is not from the configured GitHub release path')
        token=os.getenv('NOTSIP_GITHUB_TOKEN','');current=url
        async with httpx.AsyncClient(timeout=20,follow_redirects=False) as c:
            for _ in range(6):
                headers={'Accept':'text/plain'}
                if token and urlparse(current).netloc.lower()=='github.com':headers['Authorization']='Bearer '+token
                response=await c.get(current,headers=headers)
                if response.is_redirect:
                    location=response.headers.get('location','').strip()
                    if not location:raise ValueError('update SHA-256 manifest redirect did not provide a destination')
                    destination=urljoin(current,location)
                    if not self._trusted_redirect(destination):raise ValueError(f'untrusted update SHA-256 manifest redirect destination: {destination}')
                    current=destination;continue
                response.raise_for_status();text=response.text;break
            else:raise ValueError('too many update SHA-256 manifest redirects')
        match=re.search(r'\b([0-9a-fA-F]{64})\b(?:\s+\*?([^\s]+))?',text)
        if not match:raise ValueError('update SHA-256 manifest does not contain a valid digest')
        digest=match.group(1).lower();name=str(match.group(2) or '').lstrip('*')
        if name and Path(name).name.lower()!=Path(expected_name).name.lower():raise ValueError('update SHA-256 manifest names a different artifact')
        return digest
    async def download_release_asset(self,asset_name='NOTSIP.exe'):
        release=await self.check();name=Path(str(asset_name or '')).name
        asset=next((a for a in release.get('assets',[]) if a.get('name')==name),None)
        if not release.get('available'):return {'status':'NO_UPDATE','release':release}
        if asset is None:raise ValueError(f'trusted latest release does not contain {name}')
        sha_url=asset.get('sha256_url')
        if not sha_url:raise ValueError(f'trusted latest release does not publish a SHA-256 manifest for {name}')
        digest=await self._fetch_manifest_sha(sha_url,name)
        result=await self.download(asset['url'],digest);result.update({'release_tag':release.get('tag'),'asset_name':name,'manifest_url':sha_url});return result
    async def download(self,asset_url:str,sha256:str=''):
        if not self._trusted_asset(asset_url):raise ValueError('update asset is not from the configured GitHub release path or is not an EXE')
        if not sha256 or len(sha256.strip())!=64:raise ValueError('update SHA-256 is required')
        token=os.getenv('NOTSIP_GITHUB_TOKEN','');current_url=asset_url;target=self.dir/f'update-{uuid.uuid4().hex}.exe';response=None
        async with httpx.AsyncClient(timeout=120,follow_redirects=False) as c:
            for _ in range(6):
                headers={'Accept':'application/octet-stream'}
                if token and urlparse(current_url).netloc.lower()=='github.com':headers['Authorization']='Bearer '+token
                response=await c.get(current_url,headers=headers)
                if response.is_redirect:
                    location=response.headers.get('location','').strip()
                    if not location:raise ValueError('update redirect did not provide a destination')
                    destination=urljoin(current_url,location)
                    if not self._trusted_redirect(destination):raise ValueError(f'untrusted update redirect destination: {destination}')
                    current_url=destination;continue
                response.raise_for_status();break
            else:raise ValueError('too many update redirects')
            target.write_bytes(response.content)
        digest=hashlib.sha256(target.read_bytes()).hexdigest()
        if digest.lower()!=sha256.lower():target.unlink(missing_ok=True);raise ValueError('update SHA-256 verification failed')
        return {'status':'DOWNLOADED','path':str(target),'sha256':digest,'download_host':urlparse(current_url).hostname}
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
        new_path=self._managed_update_path(new_exe);signer=self._verify_authenticode(new_path)
        if signer.get('status')!='VALID':raise RuntimeError(signer.get('reason','publisher verification unavailable'))
        suffix=uuid.uuid4().hex;backup=self.dir/f'previous-{suffix}.exe';helper=self.dir/f'apply-{suffix}.ps1';shutil.copy2(current,backup);new_s=self._powershell_quote(new_path);cur_s=self._powershell_quote(current);backup_s=self._powershell_quote(backup);health_s=self._powershell_quote(self.health_url);pid=os.getpid()
        helper.write_text(f'''param()\n$ErrorActionPreference="Stop"\nStart-Sleep -Seconds 1\ntry {{ Stop-Process -Id {pid} -Force -ErrorAction Stop }} catch {{ if($_.Exception.Message -notmatch "not found|cannot find"){{ throw }} }}\nStart-Sleep -Milliseconds 750\ntry {{ Copy-Item -Force {new_s} {cur_s}; Start-Process {cur_s}; Start-Sleep -Seconds 4; $r=Invoke-WebRequest {health_s} -UseBasicParsing -TimeoutSec 5; if($r.StatusCode -ne 200){{ throw "health check returned HTTP $($r.StatusCode)" }}; Remove-Item -Force {backup_s} -ErrorAction SilentlyContinue }} catch {{ try {{ Copy-Item -Force {backup_s} {cur_s}; Start-Process {cur_s} }} catch {{ }}; exit 2 }}\n''',encoding='utf-8');subprocess.Popen(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(helper)],creationflags=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0));return {'status':'STAGED','backup':str(backup),'restart_required':True,'publisher':signer,'health_url':self.health_url}
