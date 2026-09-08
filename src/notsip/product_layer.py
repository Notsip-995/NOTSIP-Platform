from __future__ import annotations
import base64,binascii,hashlib,json,os,platform,shutil,socket,subprocess,sys,tempfile,time,uuid,zipfile,threading
from pathlib import Path
from .actor_context import current_actor
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
    def __init__(self,name='NOTSIP',root=None):self.root=Path(root or os.getenv('NOTSIP_DATA_DIR','./data')).resolve();self.path=self.root/'runtime'/'instance.lock';self.path.parent.mkdir(parents=True,exist_ok=True);self._owned=False
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
    SECRET_NAMES={'api_key','event_hmac_secret','pairing_secret','llm_api_key','fallback_llm_api_key','stt_api_key','tts_api_key','email_password','oidc_client_secret','oauth_client_secret','node_shared_secret','brave_api_key','database_url','business_admin_token','flight_planning_token','remote_compute_token','remote_sensing_token','home_adapter_token','biometric_adapter_token','speaker_identity_token'}
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
    def __init__(self,root):self.path=Path(root)/'runtime'/'audit.jsonl';self.path.parent.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock()
    def _last_hash(self):
        if not self.path.exists():return '0'*64
        lines=self.path.read_text(encoding='utf-8').splitlines()
        for line in reversed(lines):
            if not line.strip():continue
            try:
                row=json.loads(line);digest=str(row.get('digest',''))
            except json.JSONDecodeError as exc:raise RuntimeError('audit log is corrupt; refusing to append') from exc
            if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest.lower()):raise RuntimeError('audit log contains an invalid digest; refusing to append')
            return digest
        return '0'*64
    def write(self,event,**fields):
        with self.lock:
            row={'ts':time.time(),'event':event,**fields};row['prev_digest']=self._last_hash();canonical=json.dumps(row,sort_keys=True,separators=(',',':'),default=str);row['digest']=hashlib.sha256(canonical.encode()).hexdigest()
            with self.path.open('a',encoding='utf-8') as f:f.write(json.dumps(row,sort_keys=True,separators=(',',':'),default=str)+'\n')
    def verify(self):
        if not self.path.exists():return {'valid':True,'entries':0}
        previous='0'*64;entries=0
        try:
            for raw in self.path.read_text(encoding='utf-8').splitlines():
                if not raw.strip():continue
                row=json.loads(raw);digest=str(row.get('digest',''));stored_prev=str(row.get('prev_digest',''));unsigned=dict(row);unsigned.pop('digest',None);canonical=json.dumps(unsigned,sort_keys=True,separators=(',',':'),default=str);actual=hashlib.sha256(canonical.encode()).hexdigest()
                if stored_prev!=previous or digest!=actual:return {'valid':False,'entries':entries,'reason':'audit hash chain verification failed','failed_entry':entries+1}
                previous=digest;entries+=1
            return {'valid':True,'entries':entries,'head':previous}
        except Exception as exc:return {'valid':False,'entries':entries,'reason':f'audit verification error: {exc}','failed_entry':entries+1}
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
                if rel.parts and rel.parts[0] in {'backups','master.key'}:continue
                if rel.as_posix().startswith('runtime/') and rel.name=='master.key':continue
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
            stage=Path(tempfile.mkdtemp(prefix='notsip-restore-',dir=self.root.parent));rollback=Path(tempfile.mkdtemp(prefix='notsip-rollback-',dir=self.root.parent));changes=[]
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
                    backup_target=rollback/item.name;existed=target.exists();changes.append((target,backup_target,existed))
                    if existed:shutil.move(str(target),str(backup_target))
                    try:shutil.move(str(item),str(target))
                    except Exception:
                        if existed and backup_target.exists():shutil.move(str(backup_target),str(target))
                        raise
                return {'status':'SUCCESS','restored':name,'restart_required':True}
            except Exception:
                for target,backup_target,existed in reversed(changes):
                    try:
                        if target.exists():shutil.rmtree(target) if target.is_dir() else target.unlink()
                        if existed and backup_target.exists():target.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(backup_target),str(target))
                    except Exception:pass
                raise
            finally:shutil.rmtree(stage,ignore_errors=True);shutil.rmtree(rollback,ignore_errors=True)

class ApprovalStore:
    def __init__(self,root):self.path=Path(root)/'runtime'/'approvals.json';self.path.parent.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock()
    def _load(self):
        if not self.path.exists():return {}
        try:data=json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError,json.JSONDecodeError) as exc:raise RuntimeError('approval store is corrupt; refusing to treat it as empty') from exc
        if not isinstance(data,dict):raise RuntimeError('approval store has invalid structure')
        return data
    def _save(self,d):tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(d,indent=2,sort_keys=True));os.replace(tmp,self.path)
    @staticmethod
    def _actor(context,actor=None):return str(actor or (context or {}).get('actor') or current_actor()).strip() or 'primary-user'
    def request(self,action,reason,context=None,ttl=900,actor=None):
        with self.lock:
            d=self._load();aid=uuid.uuid4().hex;ctx=dict(context or {});ctx['actor']=self._actor(ctx,actor);d[aid]={'id':aid,'action':action,'reason':reason,'context':ctx,'status':'PENDING','expires':time.time()+ttl};self._save(d);return d[aid]
    def decide(self,aid,approved,actor=None):
        with self.lock:
            d=self._load();x=d.get(aid)
            if not x:return None
            expected=self._actor(x.get('context') or {},actor)
            if expected!=current_actor():return None
            if x.get('status')!='PENDING':return x
            if float(x.get('expires',0))<=time.time():x['status']='EXPIRED';x['decided']=time.time();self._save(d);return x
            x['status']='APPROVED' if approved else 'REJECTED';x['decided']=time.time();self._save(d);return x
    def pending(self,actor=None):
        actor=self._actor({},actor)
        with self.lock:
            out=[];now=time.time()
            for x in self._load().values():
                if x.get('status')=='PENDING' and x.get('expires',0)>now and self._actor(x.get('context') or {},actor)==actor:out.append(x)
            return out

class Diagnostics:
    def __init__(self,root,settings=None,store=None,provider=None,web=None,email=None,auth=None,nodes=None,recovery=None):self.root=Path(root);self.settings=settings;self.store=store;self.provider=provider;self.web=web;self.email=email;self.auth=auth;self.nodes=nodes;self.recovery=recovery
    def run(self):
        s=self.settings;checks={'python':{'ok':sys.version_info[:2]>=(3,12),'detail':sys.version},'platform':{'ok':True,'detail':platform.platform()},'storage':{'ok':self.root.exists() and os.access(self.root,os.W_OK),'detail':str(self.root)}}
        if self.store:
            try:self.store.row('SELECT 1');checks['database']={'ok':True,'detail':'connected'}
            except Exception as e:checks['database']={'ok':False,'detail':str(e)}
        checks['llm']={'ok':bool(self.provider and (self.provider.enabled or self.provider.fallback_enabled)),'detail':'primary/fallback configured' if self.provider and (self.provider.enabled or self.provider.fallback_enabled) else 'not configured'};checks['stt']={'ok':bool(s and s.stt_base_url and s.stt_model),'detail':'configured' if s and s.stt_base_url and s.stt_model else 'not configured'};checks['tts']={'ok':bool(s and s.tts_base_url and s.tts_model),'detail':'configured' if s and s.tts_base_url and s.tts_model else 'not configured'};checks['vision']={'ok':bool(s and s.vision_enabled),'detail':'enabled' if s and s.vision_enabled else 'disabled'};checks['web_search']={'ok':bool(self.web and self.web.enabled),'detail':'configured' if self.web and self.web.enabled else 'not configured'};checks['email']={'ok':bool(self.email and self.email.enabled),'detail':'configured' if self.email and self.email.enabled else 'not configured'};checks['oauth']={'ok':bool(self.auth and self.auth.oidc.configured),'detail':'configured' if self.auth and self.auth.oidc.configured else 'not configured'};checks['browser']={'ok':bool(getattr(s,'browser_enabled',True)),'detail':'enabled' if getattr(s,'browser_enabled',True) else 'disabled'};checks['windows_uia']={'ok':platform.system()=='Windows','detail':'ready' if platform.system()=='Windows' else 'Windows node required'};checks['android']={'ok':bool(self.store and self.store.devices()),'detail':'paired device present' if self.store and self.store.devices() else 'no paired Android device'};checks['scheduler']={'ok':True,'detail':'durable scheduler available'};checks['federation']={'ok':bool(self.nodes),'detail':'node registry available' if self.nodes else 'not initialized'};checks['recovery']={'ok':True,'detail':'checkpoint available' if self.recovery and self.recovery.verify_latest()['valid'] else 'checkpoint not yet created'};checks['security']={'ok':bool(self.auth),'detail':'security manager initialized' if self.auth else 'security manager unavailable'}
        core_names={'python','platform','storage','database','llm','scheduler','federation','security'};optional_names=set(checks)-core_names;core_ok=all(checks[k]['ok'] for k in core_names if k in checks);optional_missing=[k for k in optional_names if not checks[k]['ok']]
        return {'ok':core_ok,'core_ok':core_ok,'optional_missing':optional_missing,'checks':checks,'timestamp':time.time()}

class CapabilityProbe:
    """Report configured and available product capabilities without inventing readiness."""
    def __init__(self,settings=None,store=None,provider=None,web=None,email=None):self.settings=settings;self.store=store;self.provider=provider;self.web=web;self.email=email
    def snapshot(self):
        s=self.settings
        checks={
            'llm': bool(self.provider and (self.provider.enabled or self.provider.fallback_enabled)),
            'web_search': bool(self.web and self.web.enabled),
            'email': bool(self.email and self.email.enabled),
            'android': bool(self.store and self.store.devices()),
            'windows_uia': platform.system()=='Windows',
            'database': bool(self.store),
            'stt': bool(s and s.stt_base_url and s.stt_model),
            'tts': bool(s and s.tts_base_url and s.tts_model),
            'vision': bool(s and s.vision_enabled),
            'browser': bool(getattr(s,'browser_enabled',True)),
            'federation': bool(getattr(s,'node_lease_seconds',0)),
        }
        return {'capabilities':checks,'available':[k for k,v in checks.items() if v],'unavailable':[k for k,v in checks.items() if not v],'timestamp':time.time()}

class Maintenance:
    def __init__(self,root):self.root=Path(root).resolve()
    def inventory(self):
        import hashlib;out=[]
        for p in self.root.rglob('*'):
            if p.is_file():
                try:out.append({'path':str(p.relative_to(self.root)).replace('\\','/'),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
                except Exception:pass
        return out[:10000]
    def read(self,path):
        p=(self.root/path).resolve()
        if self.root not in p.parents:raise ValueError('path outside repository')
        return p.read_text(encoding='utf-8')
    def verify(self):
        if not (self.root/'.git').exists():return {'status':'UNAVAILABLE','reason':'durable Git checkout required','root':str(self.root)}
        r=subprocess.run(['git','-C',str(self.root),'status','--porcelain'],capture_output=True,text=True);tests=subprocess.run([sys.executable,'-m','pytest','-q'],cwd=self.root,capture_output=True,text=True,timeout=600)
        return {'status':'PASS' if tests.returncode==0 else 'FAILURE','clean':not bool(r.stdout.strip()),'tests_exit':tests.returncode,'stdout':tests.stdout[-12000:],'stderr':tests.stderr[-12000:]}
