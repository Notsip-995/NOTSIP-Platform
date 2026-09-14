from __future__ import annotations
import base64,binascii,hashlib,json,os,platform,shutil,socket,subprocess,sys,tempfile,time,uuid,zipfile,threading
from pathlib import Path
from .actor_context import actor_is_explicit,current_actor
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
            try:raw=self.path.read_text(encoding='utf-8');data=json.loads(raw)
            except FileNotFoundError:return self.acquire()
            except (OSError,json.JSONDecodeError,ValueError) as exc:raise RuntimeError('instance lock is corrupt or unreadable; refusing to remove it automatically') from exc
            pid=int(data.get('pid') or 0);host=str(data.get('host') or '')
            if pid<=0 or not host:raise RuntimeError('instance lock is missing required ownership metadata')
            if host==socket.gethostname() and self._pid_alive(pid):return False
            if host!=socket.gethostname():raise RuntimeError('instance lock belongs to another host; refusing automatic takeover')
            try:self.path.unlink()
            except FileNotFoundError:return self.acquire()
            except OSError as exc:raise RuntimeError('unable to remove stale NOTSIP instance lock') from exc
            return self.acquire()
    @staticmethod
    def _pid_alive(pid):
        if platform.system()=='Windows':return str(pid) in subprocess.run(['tasklist','/FI',f'PID eq {pid}','/NH'],capture_output=True,text=True,timeout=5).stdout
        try:os.kill(pid,0);return True
        except ProcessLookupError:return False
        except PermissionError:return True
        except OSError:return False
    def release(self):
        if self._owned:
            try:self.path.unlink()
            except FileNotFoundError:self._owned=False
            else:self._owned=False

class ConfigStore:
    SECRET_NAMES={'api_key','event_hmac_secret','pairing_secret','llm_api_key','fallback_llm_api_key','stt_api_key','tts_api_key','email_password','oidc_client_secret','oauth_client_secret','node_shared_secret','brave_api_key','database_url','business_admin_token','flight_planning_token','remote_compute_token','remote_sensing_token','home_adapter_token','biometric_adapter_token','speaker_identity_token'}
    DATABASE_SECRET='NOTSIP_DATABASE_URL'
    def __init__(self,root):self.root=Path(root);self.path=self.root/'config.json';self.root.mkdir(parents=True,exist_ok=True)
    def _secret_store(self):
        from .security import SecretStore
        return SecretStore(self.root)
    def load(self):
        legacy_db=None
        if not self.path.exists():data={'version':CONFIG_VERSION,'settings':{}}
        else:
            data=self.migrate(json.loads(self.path.read_text(encoding='utf-8')))
            legacy_db=(data.get('settings') or {}).get('database_url')
        stored=self._secret_store().get(self.DATABASE_SECRET)
        if stored:data['settings']['database_url']=stored
        elif legacy_db:data['settings']['database_url']=legacy_db
        if legacy_db:
            self._secret_store().set(self.DATABASE_SECRET,str(legacy_db));data['settings'].pop('database_url',None);data['settings']['database_url']=legacy_db;self._write_clean(data['settings'])
        return data
    def _write_clean(self,settings):
        clean={k:v for k,v in dict(settings or {}).items() if k not in self.SECRET_NAMES and k!='database_url'};tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps({'version':CONFIG_VERSION,'settings':clean,'updated_at':time.time()},indent=2,sort_keys=True));os.replace(tmp,self.path)
    def migrate(self,d):
        if int(d.get('version',1))<CONFIG_VERSION:d['migrated_from']=d.get('version',1)
        d['version']=CONFIG_VERSION;d.setdefault('settings',{});d['migrated_at']=d.get('migrated_at',time.time());return d
    def save(self,settings):
        settings=dict(settings or {});database_url=settings.pop('database_url',None);secret_store=self._secret_store()
        if database_url is not None:
            if str(database_url).strip():secret_store.set(self.DATABASE_SECRET,str(database_url))
            else:secret_store.delete(self.DATABASE_SECRET)
        self._write_clean(settings)
    def backup(self):
        if not self.path.exists():self.save({})
        dst=self.root/'runtime'/f'config-{time.strftime("%Y%m%d-%H%M%S")}.json';dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(self.path,dst);return str(dst.relative_to(self.root))

class _FileLock:
    """Portable advisory exclusive lock used to serialize audit-log append
    across processes. Uses fcntl on POSIX and msvcrt on Windows; degrades to
    a no-op when neither is available so the audit path never hard-fails."""
    def __init__(self,path):self.path=str(path);self._fd=None
    def acquire(self):
        try:
            import fcntl  # type: ignore
            self._fd=os.open(self.path,os.O_CREAT|os.O_RDWR,0o600)
            fcntl.flock(self._fd,fcntl.LOCK_EX)
            return
        except (ImportError,OSError,ValueError):
            self._fd=None
        try:
            import msvcrt  # type: ignore
            self._fd=os.open(self.path,os.O_CREAT|os.O_RDWR,0o600)
            if os.fstat(self._fd).st_size==0:
                os.write(self._fd,b'0')
            os.lseek(self._fd,0,os.SEEK_SET)
            msvcrt.locking(self._fd,msvcrt.LK_LOCK,1)
        except (ImportError,OSError,ValueError):
            self._fd=None
    def release(self):
        if self._fd is None:return
        try:
            import fcntl  # type: ignore
            fcntl.flock(self._fd,fcntl.LOCK_UN)
        except ImportError:
            try:
                import msvcrt  # type: ignore
                try:
                    os.lseek(self._fd,0,os.SEEK_SET)
                    msvcrt.locking(self._fd,msvcrt.LK_UNLCK,1)
                except OSError:pass
            except ImportError:pass
        except OSError:pass
        try:os.close(self._fd)
        except OSError:pass
        self._fd=None

class AuditLog:
    def __init__(self,root):self.path=Path(root)/'runtime'/'audit.jsonl';self.path.parent.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock();self._flock=_FileLock(self.path.with_suffix('.lock'))
    @staticmethod
    def _digest(row):
        unsigned=dict(row);unsigned.pop('digest',None);return hashlib.sha256(json.dumps(unsigned,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()
    def verify(self):
        if not self.path.exists():return {'valid':True,'entries':0,'head':'0'*64}
        previous='0'*64;entries=0
        try:
            for raw in self.path.read_text(encoding='utf-8').splitlines():
                if not raw.strip():continue
                try:row=json.loads(raw)
                except json.JSONDecodeError as exc:return {'valid':False,'entries':entries,'reason':f'audit log is corrupt: {exc}','failed_entry':entries+1}
                digest=str(row.get('digest',''));stored_prev=str(row.get('prev_digest',''))
                if stored_prev!=previous or digest!=self._digest(row):return {'valid':False,'entries':entries,'reason':'audit hash chain verification failed','failed_entry':entries+1}
                previous=digest;entries+=1
            return {'valid':True,'entries':entries,'head':previous}
        except OSError as exc:return {'valid':False,'entries':entries,'reason':f'audit log read failed: {exc}','failed_entry':entries+1}
    def recover(self):
        """Quarantine a corrupt/tampered audit log and restart an empty chain.

        Run explicitly at process startup so a log corrupted by a previous
        crash or a concurrent-writer race does not make the product unusable.
        The invalid file is delivered to runtime/quarantine/ (preserving
        evidence) and an 'audit.chain.reset' entry records the recovery before
        any request writes. Returns {'recovered': bool, 'reason': str|None,
        'quarantined': str|None, 'entries': int}."""
        with self.lock:
            self._flock.acquire()
            try:
                result=self.verify()
                if result['valid']:return {'recovered':False,'reason':None,'quarantined':None,'entries':result['entries']}
                qdir=self.path.parent/'quarantine';qdir.mkdir(parents=True,exist_ok=True)
                dest=qdir/f'audit-{time.strftime("%Y%m%d-%H%M%S")}.jsonl'
                quarantined=None
                if self.path.exists():
                    try:os.replace(self.path,dest);quarantined=str(dest.relative_to(self.path.parent.parent))
                    except OSError:
                        dest=qdir/f'audit-{time.strftime("%Y%m%d-%H%M%S")}-{uuid.uuid4().hex[:8]}.jsonl'
                        try:os.replace(self.path,dest);quarantined=str(dest.relative_to(self.path.parent.parent))
                        except OSError:quarantined=None
                row={'ts':time.time(),'event':'audit.chain.reset','reason':result.get('reason','audit hash chain verification failed'),'quarantined':quarantined,'repair':True};row['prev_digest']='0'*64;row['digest']=self._digest(row)
                with self.path.open('a',encoding='utf-8') as f:f.write(json.dumps(row,sort_keys=True,separators=(',',':'),default=str)+'\n')
                return {'recovered':True,'reason':result.get('reason'),'quarantined':quarantined,'entries':0}
            finally:
                self._flock.release()
    def _last_hash(self):
        result=self.verify()
        if not result['valid']:raise RuntimeError(result.get('reason','audit log integrity verification failed'))
        return result.get('head','0'*64)
    def write(self,event,**fields):
        with self.lock:
            self._flock.acquire()
            try:
                row={'ts':time.time(),'event':event,**fields};row['prev_digest']=self._last_hash();row['digest']=self._digest(row)
                with self.path.open('a',encoding='utf-8') as f:f.write(json.dumps(row,sort_keys=True,separators=(',',':'),default=str)+'\n')
            finally:
                self._flock.release()
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
                    except Exception:raise
                return {'status':'SUCCESS','restored':name,'restart_required':True}
            except Exception as exc:
                rollback_errors=[]
                for target,backup_target,existed in reversed(changes):
                    try:
                        if target.exists():shutil.rmtree(target) if target.is_dir() else target.unlink()
                        if existed and backup_target.exists():target.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(backup_target),str(target))
                    except (OSError,shutil.Error) as rollback_exc:rollback_errors.append(f'{target}: {rollback_exc}')
                if rollback_errors:raise RuntimeError('backup restore failed and rollback is incomplete: '+'; '.join(rollback_errors)) from exc
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
    def _current_actor(actor=None):
        current=current_actor()
        if actor is not None and str(actor).strip()!=current:raise PermissionError('approval actor must match authenticated actor')
        return current
    def request(self,action,reason,context=None,ttl=900,actor=None):
        with self.lock:
            current=self._current_actor(actor);d=self._load();aid=uuid.uuid4().hex;ctx=dict(context or {});requested=str(ctx.get('actor') or current).strip() or current
            if requested!=current:raise PermissionError('approval actor must match authenticated actor')
            ctx['actor']=current;d[aid]={'id':aid,'action':action,'reason':reason,'context':ctx,'status':'PENDING','expires':time.time()+ttl};self._save(d);return d[aid]
    def decide(self,aid,approved,actor=None):
        with self.lock:
            current=self._current_actor(actor);d=self._load();x=d.get(aid)
            if not x:return None
            expected=str((x.get('context') or {}).get('actor') or 'primary-user')
            if expected!=current:return None
            if x.get('status')!='PENDING':return x
            if float(x.get('expires',0))<=time.time():x['status']='EXPIRED';x['decided']=time.time();self._save(d);return x
            x['status']='APPROVED' if approved else 'REJECTED';x['decided']=time.time();self._save(d);return x
    def pending(self,actor=None):
        current=self._current_actor(actor)
        unrestricted=actor is None and not actor_is_explicit()
        with self.lock:
            out=[];now=time.time()
            for x in self._load().values():
                if x.get('status')!='PENDING' or float(x.get('expires',0))<=now:continue
                owner=str((x.get('context') or {}).get('actor') or 'primary-user')
                if unrestricted or owner==current:out.append(x)
            return out

class Diagnostics:
    def __init__(self,root,settings=None,store=None,provider=None,web=None,email=None,auth=None,nodes=None,recovery=None):self.root=Path(root);self.settings=settings;self.store=store;self.provider=provider;self.web=web;self.email=email;self.auth=auth;self.nodes=nodes;self.recovery=recovery
    def run(self):
        s=self.settings;checks={'python':{'ok':sys.version_info[:2]>=(3,12),'detail':sys.version},'platform':{'ok':True,'detail':platform.platform()},'storage':{'ok':self.root.exists() and os.access(self.root,os.W_OK),'detail':str(self.root)}}
        if self.store:
            try:self.store.row('SELECT 1');checks['database']={'ok':True,'detail':'connected'}
            except Exception as e:checks['database']={'ok':False,'detail':str(e)}
        checks['llm']={'ok':bool(self.provider and (self.provider.enabled or self.provider.fallback_enabled)),'detail':'primary/fallback configured' if self.provider and (self.provider.enabled or self.provider.fallback_enabled) else 'not configured'};checks['stt']={'ok':bool(s and s.stt_base_url and s.stt_model),'detail':'configured' if s and s.stt_base_url and s.stt_model else 'not configured'};checks['tts']={'ok':bool(s and s.tts_base_url and s.tts_model),'detail':'configured' if s and s.tts_base_url and s.tts_model else 'not configured'};checks['vision']={'ok':bool(s and s.vision_enabled),'detail':'enabled' if s and s.vision_enabled else 'disabled'};checks['web_search']={'ok':bool(self.web and self.web.enabled),'detail':'configured' if self.web and self.web.enabled else 'not configured'};checks['email']={'ok':bool(self.email and self.email.enabled),'detail':'configured' if self.email and self.email.enabled else 'not configured'};checks['oauth']={'ok':bool(self.auth and self.auth.oidc.configured),'detail':'configured' if self.auth and self.auth.oidc.configured else 'not configured'};checks['browser']={'ok':bool(s and getattr(s,'browser_enabled',True)),'detail':'enabled' if s and getattr(s,'browser_enabled',True) else 'disabled'};checks['windows_uia']={'ok':platform.system()=='Windows','detail':'ready' if platform.system()=='Windows' else 'Windows node required'};checks['android']={'ok':bool(self.store and self.store.devices()),'detail':'paired device present' if self.store and self.store.devices() else 'no paired Android device'};checks['scheduler']={'ok':True,'detail':'durable scheduler available'}
        federation_ok=False;federation_detail='node registry unavailable'
        if self.nodes:
            try:
                node_rows=self.nodes.reconcile();federation_ok=any(str(n.get('status','')).upper()=='ONLINE' for n in node_rows);federation_detail='online node available' if federation_ok else 'no online node'
            except (AttributeError,TypeError,ValueError,RuntimeError) as exc:federation_detail=f'node registry unavailable: {exc}'
        checks['federation']={'ok':federation_ok,'detail':federation_detail};recovery_ok=False
        if self.recovery:
            try:recovery_ok=bool(self.recovery.verify_latest().get('valid'))
            except (AttributeError,TypeError,ValueError,RuntimeError):recovery_ok=False
        checks['recovery']={'ok':recovery_ok,'detail':'checkpoint available' if recovery_ok else 'checkpoint not yet created'};checks['security']={'ok':bool(self.auth),'detail':'security manager initialized' if self.auth else 'security manager unavailable'}
        core_names={'python','platform','storage','database','llm','scheduler','federation','security'};optional_names=set(checks)-core_names;core_ok=all(checks[k]['ok'] for k in core_names if k in checks);optional_missing=[k for k in optional_names if not checks[k]['ok']]
        return {'ok':core_ok,'core_ok':core_ok,'optional_missing':optional_missing,'checks':checks,'timestamp':time.time()}

class CapabilityProbe:
    """Report configured and available product capabilities without inventing readiness."""
    def __init__(self,settings=None,store=None,provider=None,web=None,email=None,nodes=None):self.settings=settings;self.store=store;self.provider=provider;self.web=web;self.email=email;self.nodes=nodes
    def snapshot(self):
        s=self.settings;online_nodes=False
        if self.nodes is not None:
            try:online_nodes=any(str(n.get('status','')).upper()=='ONLINE' for n in self.nodes.reconcile(current_actor()))
            except (AttributeError,TypeError,ValueError,RuntimeError):online_nodes=False
        checks={'llm':bool(self.provider and (self.provider.enabled or self.provider.fallback_enabled)),'web_search':bool(self.web and self.web.enabled),'email':bool(self.email and self.email.enabled),'android':bool(self.store and self.store.devices(current_actor())),'windows_uia':platform.system()=='Windows','database':bool(self.store),'stt':bool(s and s.stt_base_url and s.stt_model),'tts':bool(s and s.tts_base_url and s.tts_model),'voice':bool(s and s.voice_enabled and s.stt_base_url and s.tts_base_url),'perception':bool(s and s.perception_enabled),'browser':bool(getattr(s,'browser_enabled',True)),'federation':online_nodes}
        return {'capabilities':checks,'available':[k for k,v in checks.items() if v],'unavailable':[k for k,v in checks.items() if not v],'timestamp':time.time()}

class Maintenance:
    def __init__(self,root):self.root=Path(root).resolve()
    def inventory(self):
        import hashlib;out=[]
        for p in self.root.rglob('*'):
            if p.is_file():
                try:out.append({'path':str(p.relative_to(self.root)).replace('\\','/'),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
                except (OSError,ValueError) as exc:raise RuntimeError(f'unable to hash repository file {p}: {exc}') from exc
        return out[:10000]
    def read(self,path):
        p=(self.root/path).resolve()
        if self.root not in p.parents:raise ValueError('path outside repository')
        return p.read_text(encoding='utf-8')
    def verify(self):
        if not (self.root/'.git').exists():return {'status':'UNAVAILABLE','reason':'durable Git checkout required','root':str(self.root)}
        r=subprocess.run(['git','-C',str(self.root),'status','--porcelain'],capture_output=True,text=True);tests=subprocess.run([sys.executable,'-m','pytest','-q'],cwd=self.root,capture_output=True,text=True,timeout=600)
        return {'status':'PASS' if tests.returncode==0 else 'FAILURE','clean':not bool(r.stdout.strip()),'tests_exit':tests.returncode,'stdout':tests.stdout[-12000:],'stderr':tests.stderr[-12000:]}
    def apply_patch(self,patch_text,confirmation):
        from .self_maintenance import SelfMaintenance
        return SelfMaintenance(self.root).apply_patch(patch_text,confirmation)
