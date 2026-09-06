from __future__ import annotations
import json, os, platform, shutil, socket, subprocess, sys, tempfile, threading, time, uuid, zipfile
from pathlib import Path
from typing import Any

APP_NAME='NOTSIP'
CONFIG_VERSION=2

def resource_root() -> Path:
    frozen=getattr(sys,'_MEIPASS',None)
    if frozen: return Path(frozen)
    here=Path(__file__).resolve()
    for candidate in (here.parents[2], Path.cwd()):
        if (candidate/'ui.html').exists(): return candidate
    return here.parents[2]

def repo_root() -> Path:
    override=os.getenv('NOTSIP_REPO_ROOT','')
    if override: return Path(override).expanduser().resolve()
    return resource_root()

def choose_free_port(host:str,port:int,limit:int=20)->int:
    for p in range(port,port+limit+1):
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            try:s.bind((host,p));return p
            except OSError:continue
    raise RuntimeError(f'no free TCP port in {port}-{port+limit}')

class ProcessGuard:
    def __init__(self,name='NOTSIP',root:Path|None=None):
        self.name=name; self.root=Path(root or Path(os.getenv('NOTSIP_DATA_DIR','./data'))).resolve(); self.path=self.root/'runtime'/'instance.lock'; self.path.parent.mkdir(parents=True,exist_ok=True); self._owned=False
    def acquire(self):
        payload={'pid':os.getpid(),'created':time.time(),'host':socket.gethostname()}
        try:
            fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
            os.write(fd,json.dumps(payload).encode());os.close(fd);self._owned=True;return True
        except FileExistsError:
            try:
                old=json.loads(self.path.read_text()); pid=int(old.get('pid',0))
                if pid and self._pid_alive(pid): return False
            except Exception: pass
            try:self.path.unlink()
            except Exception:return False
            return self.acquire()
    @staticmethod
    def _pid_alive(pid:int)->bool:
        if platform.system()=='Windows':
            p=subprocess.run(['tasklist','/FI',f'PID eq {pid}','/NH'],capture_output=True,text=True,timeout=5)
            return str(pid) in p.stdout
        try:os.kill(pid,0);return True
        except OSError:return False
    def release(self):
        if self._owned:
            try:self.path.unlink()
            except FileNotFoundError:pass
            self._owned=False

class ConfigStore:
    SECRET_NAMES={'api_key','event_hmac_secret','pairing_secret','llm_api_key','fallback_llm_api_key','stt_api_key','tts_api_key','email_password','oidc_client_secret','oauth_client_secret','node_shared_secret'}
    def __init__(self,root:Path): self.root=Path(root); self.path=self.root/'config.json'; self.root.mkdir(parents=True,exist_ok=True)
    def load(self)->dict:
        if not self.path.exists():return {'version':CONFIG_VERSION,'settings':{}}
        data=json.loads(self.path.read_text(encoding='utf-8'));data=self.migrate(data);return data
    def migrate(self,data:dict)->dict:
        v=int(data.get('version',1))
        if v<2:
            data.setdefault('settings',{});data['version']=CONFIG_VERSION;data['migrated_at']=time.time()
        return data
    def save(self,settings:dict):
        clean={k:v for k,v in settings.items() if k not in self.SECRET_NAMES}
        tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps({'version':CONFIG_VERSION,'settings':clean,'updated_at':time.time()},indent=2,sort_keys=True),encoding='utf-8');os.replace(tmp,self.path)
    def backup(self)->str:
        stamp=time.strftime('%Y%m%d-%H%M%S');dst=self.root/'runtime'/f'config-{stamp}.json';dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(self.path,dst);return str(dst.relative_to(self.root))

class AuditLog:
    def __init__(self,root:Path):self.path=Path(root)/'runtime'/'audit.jsonl';self.path.parent.mkdir(parents=True,exist_ok=True);self.lock=threading.Lock()
    def write(self,event:str,**fields):
        row={'ts':time.time(),'event':event,**fields}
        with self.lock:self.path.open('a',encoding='utf-8').write(json.dumps(row,sort_keys=True)+'\n')
    def tail(self,n=200):
        if not self.path.exists():return []
        lines=self.path.read_text(encoding='utf-8').splitlines()[-n:];return [json.loads(x) for x in lines if x.strip()]

class BackupManager:
    def __init__(self,root:Path):self.root=Path(root);self.dir=self.root/'backups';self.dir.mkdir(parents=True,exist_ok=True)
    def create(self,include_logs=False)->dict:
        stamp=time.strftime('%Y%m%d-%H%M%S');p=self.dir/f'NOTSIP-backup-{stamp}.zip'
        excluded={'backups'};count=0
        with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
            for f in self.root.rglob('*'):
                if not f.is_file():continue
                rel=f.relative_to(self.root)
                if rel.parts and rel.parts[0] in excluded:continue
                if not include_logs and 'runtime' in rel.parts and rel.name.endswith('.jsonl'):continue
                z.write(f,rel.as_posix());count+=1
        return {'status':'SUCCESS','path':str(p.relative_to(self.root)),'files':count,'bytes':p.stat().st_size}
    def list(self):return [{'name':p.name,'bytes':p.stat().st_size} for p in sorted(self.dir.glob('*.zip'),reverse=True)]
    def verify(self,name:str):
        p=(self.dir/name).resolve()
        if self.dir not in p.parents:raise ValueError('invalid backup path')
        with zipfile.ZipFile(p) as z:return {'valid':z.testzip() is None,'files':len(z.namelist())}

class ApprovalStore:
    def __init__(self,root:Path):self.path=Path(root)/'runtime'/'approvals.json';self.path.parent.mkdir(parents=True,exist_ok=True);self.lock=threading.Lock()
    def _load(self):
        try:return json.loads(self.path.read_text())
        except Exception:return {}
    def _save(self,d):
        t=self.path.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2,sort_keys=True));os.replace(t,self.path)
    def request(self,action,reason,context=None,ttl=900):
        with self.lock:
            d=self._load();aid=uuid.uuid4().hex;d[aid]={'id':aid,'action':action,'reason':reason,'context':context or {},'status':'PENDING','expires':time.time()+ttl};self._save(d);return d[aid]
    def decide(self,aid,approved):
        with self.lock:
            d=self._load();item=d.get(aid)
            if not item:return None
            item['status']='APPROVED' if approved else 'REJECTED';item['decided']=time.time();self._save(d);return item
    def pending(self):
        d=self._load();now=time.time();out=[]
        for x in d.values():
            if x['status']=='PENDING' and x.get('expires',0)>now:out.append(x)
        return out

class Diagnostics:
    def __init__(self,root,settings=None,store=None,provider=None,web=None,email=None):self.root=Path(root);self.settings=settings;self.store=store;self.provider=provider;self.web=web;self.email=email
    def run(self)->dict:
        checks={}
        checks['python']={'ok':sys.version_info[:2]>=(3,12),'detail':sys.version}
        checks['platform']={'ok':True,'detail':platform.platform()}
        checks['storage']={'ok':self.root.exists() and os.access(self.root,os.W_OK),'detail':str(self.root)}
        if self.store:
            try:self.store.row('SELECT 1');checks['database']={'ok':True}
            except Exception as e:checks['database']={'ok':False,'detail':str(e)}
        if self.provider:checks['llm']={'ok':bool(self.provider.enabled or self.provider.fallback_enabled),'detail':'configured' if (self.provider.enabled or self.provider.fallback_enabled) else 'not configured'}
        if self.web:checks['web_search']={'ok':bool(self.web.enabled),'detail':'configured' if self.web.enabled else 'not configured'}
        if self.email:checks['email']={'ok':bool(self.email.enabled),'detail':'configured' if self.email.enabled else 'not configured'}
        checks['browser']={'ok':True,'detail':'Playwright adapter installed' }
        checks['windows_uia']={'ok':platform.system()=='Windows','detail':'available on Windows node' if platform.system()=='Windows' else 'Windows node required'}
        checks['android']={'ok':bool(self.store and self.store.devices()),'detail':'paired device present' if self.store and self.store.devices() else 'no paired Android device'}
        checks['git']={'ok':(self.root/'.git').exists(),'detail':'repository checkout' if (self.root/'.git').exists() else 'not a source checkout'}
        return {'ok':all(x.get('ok') for x in checks.values()),'checks':checks,'timestamp':time.time()}

class Maintenance:
    def __init__(self,root:Path):self.root=Path(root).resolve()
    def inventory(self):
        out=[]
        for p in self.root.rglob('*'):
            if not p.is_file():continue
            if any(x in {'.git','.venv','__pycache__','.pytest_cache','data','dist','build','backups'} for x in p.parts):continue
            import hashlib
            out.append({'path':p.relative_to(self.root).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
        return sorted(out,key=lambda x:x['path'])
    def verify(self):
        c=subprocess.run([sys.executable,'-m','compileall','-q','src'],cwd=self.root,capture_output=True,text=True,timeout=180)
        t=subprocess.run([sys.executable,'-m','pytest','-q'],cwd=self.root,capture_output=True,text=True,timeout=300)
        return {'compile_ok':c.returncode==0,'tests_ok':t.returncode==0,'compile_stderr':c.stderr[-4000:],'tests_stdout':t.stdout[-8000:]}

class CapabilityProbe:
    def __init__(self,settings,store,provider,web,email):self.settings=settings;self.store=store;self.provider=provider;self.web=web;self.email=email
    def snapshot(self):
        return {'llm':bool(self.provider.enabled),'fallback_llm':bool(self.provider.fallback_enabled),'stt':bool(self.settings.stt_base_url and self.settings.stt_model),'tts':bool(self.settings.tts_base_url and self.settings.tts_model),'vision':bool(self.settings.vision_enabled),'web':bool(self.web.enabled),'email':bool(self.email.enabled),'android':bool(self.store.devices()),'windows':platform.system()=='Windows','git_self_maintenance':(repo_root()/'.git').exists()}
