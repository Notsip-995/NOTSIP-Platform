from __future__ import annotations
import json, os, platform, shutil, socket, subprocess, sys, tempfile, time, uuid, zipfile
from pathlib import Path
APP_NAME='NOTSIP';CONFIG_VERSION=2

def resource_root()->Path:
    frozen=getattr(sys,'_MEIPASS',None)
    if frozen:return Path(frozen)
    here=Path(__file__).resolve()
    for candidate in (here.parents[2],Path.cwd()):
        if (candidate/'ui.html').exists():return candidate
    return here.parents[2]

def repo_root()->Path:
    override=os.getenv('NOTSIP_REPO_ROOT','')
    if override:return Path(override).expanduser().resolve()
    if getattr(sys,'frozen',False):
        candidate=Path(sys.executable).resolve().parent/'source'
        if candidate.exists():return candidate
    return resource_root()

def choose_free_port(host,port,limit=20):
    for p in range(int(port),int(port)+limit+1):
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
            try:s.bind((host,p));return p
            except OSError:continue
    raise RuntimeError('no free TCP port')

class ProcessGuard:
    def __init__(self,name='NOTSIP',root=None):
        self.root=Path(root or os.getenv('NOTSIP_DATA_DIR','./data')).resolve();self.path=self.root/'runtime'/'instance.lock';self.path.parent.mkdir(parents=True,exist_ok=True);self._owned=False
    def acquire(self):
        try:
            fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,json.dumps({'pid':os.getpid(),'created':time.time(),'host':socket.gethostname()}).encode());os.close(fd);self._owned=True;return True
        except FileExistsError:
            try:
                pid=int(json.loads(self.path.read_text()).get('pid',0))
                if pid and self._pid_alive(pid):return False
            except Exception:pass
            try:self.path.unlink()
            except Exception:return False
            return self.acquire()
    @staticmethod
    def _pid_alive(pid):
        if platform.system()=='Windows':return str(pid) in subprocess.run(['tasklist','/FI',f'PID eq {pid}','/NH'],capture_output=True,text=True,timeout=5).stdout
        try:os.kill(pid,0);return True
        except OSError:return False
    def release(self):
        if self._owned:
            try:self.path.unlink()
            except FileNotFoundError:pass
            self._owned=False

class ConfigStore:
    SECRET_NAMES={'api_key','event_hmac_secret','pairing_secret','llm_api_key','fallback_llm_api_key','stt_api_key','tts_api_key','email_password','oidc_client_secret','oauth_client_secret','node_shared_secret','brave_api_key','database_url'}
    def __init__(self,root):self.root=Path(root);self.path=self.root/'config.json';self.root.mkdir(parents=True,exist_ok=True)
    def load(self):
        if not self.path.exists():return {'version':CONFIG_VERSION,'settings':{}}
        d=json.loads(self.path.read_text(encoding='utf-8'));return self.migrate(d)
    def migrate(self,d):
        if int(d.get('version',1))<CONFIG_VERSION:d['migrated_from']=d.get('version',1)
        d['version']=CONFIG_VERSION;d.setdefault('settings',{});d['migrated_at']=d.get('migrated_at',time.time());return d
    def save(self,settings):
        clean={k:v for k,v in settings.items() if k not in self.SECRET_NAMES};tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps({'version':CONFIG_VERSION,'settings':clean,'updated_at':time.time()},indent=2,sort_keys=True));os.replace(tmp,self.path)
    def backup(self):
        if not self.path.exists():self.save({})
        dst=self.root/'runtime'/f'config-{time.strftime("%Y%m%d-%H%M%S")}.json';dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(self.path,dst);return str(dst.relative_to(self.root))

class AuditLog:
    def __init__(self,root):self.path=Path(root)/'runtime'/'audit.jsonl';self.path.parent.mkdir(parents=True,exist_ok=True)
    def write(self,event,**fields):
        with self.path.open('a',encoding='utf-8') as f:f.write(json.dumps({'ts':time.time(),'event':event,**fields},sort_keys=True)+'\n')
    def tail(self,n=200):
        if not self.path.exists():return []
        return [json.loads(x) for x in self.path.read_text(encoding='utf-8').splitlines()[-n:] if x.strip()]

class BackupManager:
    def __init__(self,root):self.root=Path(root);self.dir=self.root/'backups';self.dir.mkdir(parents=True,exist_ok=True)
    def create(self,include_logs=False):
        p=self.dir/f'NOTSIP-backup-{time.strftime("%Y%m%d-%H%M%S")}.zip';count=0
        with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
            for f in self.root.rglob('*'):
                if not f.is_file():continue
                rel=f.relative_to(self.root)
                if rel.parts and rel.parts[0]=='backups':continue
                if not include_logs and rel.as_posix().startswith('runtime/') and rel.suffix=='.jsonl':continue
                z.write(f,rel.as_posix());count+=1
        return {'status':'SUCCESS','path':str(p.relative_to(self.root)),'files':count,'bytes':p.stat().st_size}
    def list(self):return [{'name':p.name,'bytes':p.stat().st_size} for p in sorted(self.dir.glob('*.zip'),key=lambda x:x.stat().st_mtime,reverse=True)]
    def _safe_members(self,z):
        out=[]
        for info in z.infolist():
            name=info.filename.replace('\\','/')
            if name.startswith('/') or name.startswith('\\') or any(part=='..' for part in Path(name).parts):raise ValueError('backup contains unsafe archive path')
            out.append(info)
        return out
    def verify(self,name):
        p=(self.dir/name).resolve()
        if self.dir not in p.parents:raise ValueError('invalid backup path')
        with zipfile.ZipFile(p) as z:
            members=self._safe_members(z);return {'valid':z.testzip() is None,'files':len(members)}
    def restore(self,name,confirm=False):
        if not confirm:raise PermissionError('restore requires explicit confirmation')
        p=(self.dir/name).resolve()
        if self.dir not in p.parents:raise ValueError('invalid backup path')
        with zipfile.ZipFile(p) as z:
            members=self._safe_members(z)
            if z.testzip() is not None:raise ValueError('backup archive is corrupt')
            stage=Path(tempfile.mkdtemp(prefix='notsip-restore-',dir=self.root.parent))
            try:
                for info in members:
                    target=(stage/info.filename).resolve()
                    if stage not in target.parents and target!=stage:raise ValueError('backup contains unsafe archive path')
                    if info.is_dir():target.mkdir(parents=True,exist_ok=True);continue
                    target.parent.mkdir(parents=True,exist_ok=True)
                    with z.open(info) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst)
                for item in stage.iterdir():
                    target=self.root/item.name
                    if item.name=='backups':continue
                    if target.exists():shutil.rmtree(target) if target.is_dir() else target.unlink()
                    shutil.move(str(item),str(target))
            finally:shutil.rmtree(stage,ignore_errors=True)
        return {'status':'SUCCESS','restored':name,'restart_required':True}

class ApprovalStore:
    def __init__(self,root):self.path=Path(root)/'runtime'/'approvals.json';self.path.parent.mkdir(parents=True,exist_ok=True)
    def _load(self):
        try:return json.loads(self.path.read_text())
        except Exception:return {}
    def _save(self,d):tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(d,indent=2,sort_keys=True));os.replace(tmp,self.path)
    def request(self,action,reason,context=None,ttl=900):
        d=self._load();aid=uuid.uuid4().hex;d[aid]={'id':aid,'action':action,'reason':reason,'context':context or {},'status':'PENDING','expires':time.time()+ttl};self._save(d);return d[aid]
    def decide(self,aid,approved):
        d=self._load();x=d.get(aid)
        if not x:return None
        x['status']='APPROVED' if approved else 'REJECTED';x['decided']=time.time();self._save(d);return x
    def pending(self):return [x for x in self._load().values() if x.get('status')=='PENDING' and x.get('expires',0)>time.time()]

class Diagnostics:
    def __init__(self,root,settings=None,store=None,provider=None,web=None,email=None,auth=None,nodes=None,recovery=None):self.root=Path(root);self.settings=settings;self.store=store;self.provider=provider;self.web=web;self.email=email;self.auth=auth;self.nodes=nodes;self.recovery=recovery
    def run(self):
        s=self.settings;checks={'python':{'ok':sys.version_info[:2]>=(3,12),'detail':sys.version},'platform':{'ok':True,'detail':platform.platform()},'storage':{'ok':self.root.exists() and os.access(self.root,os.W_OK),'detail':str(self.root)}}
        if self.store:
            try:self.store.row('SELECT 1');checks['database']={'ok':True,'detail':'connected'}
            except Exception as e:checks['database']={'ok':False,'detail':str(e)}
        checks['llm']={'ok':bool(self.provider and (self.provider.enabled or self.provider.fallback_enabled)),'detail':'primary/fallback configured' if self.provider and (self.provider.enabled or self.provider.fallback_enabled) else 'not configured'}
        checks['stt']={'ok':bool(s and s.stt_base_url and s.stt_model),'detail':'configured' if s and s.stt_base_url and s.stt_model else 'not configured'}
        checks['tts']={'ok':bool(s and s.tts_base_url and s.tts_model),'detail':'configured' if s and s.tts_base_url and s.tts_model else 'not configured'}
        checks['vision']={'ok':bool(s and s.vision_enabled),'detail':'enabled' if s and s.vision_enabled else 'disabled'}
        checks['web_search']={'ok':bool(self.web and self.web.enabled),'detail':'configured' if self.web and self.web.enabled else 'not configured'}
        checks['email']={'ok':bool(self.email and self.email.enabled),'detail':'configured' if self.email and self.email.enabled else 'not configured'}
        checks['oauth']={'ok':bool(self.auth and self.auth.oidc.configured),'detail':'configured' if self.auth and self.auth.oidc.configured else 'not configured'}
        checks['browser']={'ok':bool(getattr(s,'browser_enabled',True)),'detail':'enabled' if getattr(s,'browser_enabled',True) else 'disabled'}
        checks['windows_uia']={'ok':platform.system()=='Windows','detail':'ready' if platform.system()=='Windows' else 'Windows node required'}
        checks['android']={'ok':bool(self.store and self.store.devices()),'detail':'paired device present' if self.store and self.store.devices() else 'no paired Android device'}
        checks['scheduler']={'ok':True,'detail':'durable scheduler available'}
        checks['federation']={'ok':bool(self.nodes),'detail':'node registry available' if self.nodes else 'not initialized'}
        checks['recovery']={'ok':True,'detail':'checkpoint available' if self.recovery and self.recovery.verify_latest()['valid'] else 'checkpoint not yet created'}
        checks['security']={'ok':bool(self.auth),'detail':'security manager initialized' if self.auth else 'security manager unavailable'}
        core_names={'python','platform','storage','database','llm','scheduler','federation','security'}
        optional_names=set(checks)-core_names
        core_ok=all(checks[k]['ok'] for k in core_names if k in checks)
        optional_missing=[k for k in optional_names if not checks[k]['ok']]
        return {'ok':core_ok,'core_ok':core_ok,'optional_missing':optional_missing,'checks':checks,'timestamp':time.time()}

class Maintenance:
    def __init__(self,root):self.root=Path(root).resolve()
    def inventory(self):
        import hashlib;out=[]
        for p in self.root.rglob('*'):
            if not p.is_file() or any(x in {'.git','.venv','__pycache__','.pytest_cache','data','dist','build','backups'} for x in p.parts):continue
            out.append({'path':p.relative_to(self.root).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
        return sorted(out,key=lambda x:x['path'])
    def verify(self):
        c=subprocess.run([sys.executable,'-m','compileall','-q','src'],cwd=self.root,capture_output=True,text=True,timeout=180);t=subprocess.run([sys.executable,'-m','pytest','-q'],cwd=self.root,capture_output=True,text=True,timeout=300);return {'compile_ok':c.returncode==0,'tests_ok':t.returncode==0,'compile_stderr':c.stderr[-4000:],'tests_stdout':t.stdout[-8000:]}

class CapabilityProbe:
    def __init__(self,settings,store,provider,web,email):self.settings=settings;self.store=store;self.provider=provider;self.web=web;self.email=email
    def snapshot(self):return {'llm':self.provider.enabled,'fallback_llm':self.provider.fallback_enabled,'stt':bool(self.settings.stt_base_url and self.settings.stt_model),'tts':bool(self.settings.tts_base_url and self.settings.tts_model),'vision':bool(self.settings.vision_enabled),'web':self.web.enabled,'email':self.email.enabled,'android':bool(self.store.devices()),'windows':platform.system()=='Windows','self_maintenance':True}
