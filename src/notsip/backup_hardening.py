from __future__ import annotations
import shutil,tempfile,time,uuid,zipfile
from pathlib import Path

def install(manager):
    if not getattr(manager,'_notsip_secure_backup_create',False):
        def create_safe(include_logs=False):
            p=manager.dir/f'NOTSIP-backup-{time.strftime("%Y%m%d-%H%M%S")}-{uuid.uuid4().hex[:8]}.zip';count=0
            with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
                for f in manager.root.rglob('*'):
                    if not f.is_file():continue
                    rel=f.relative_to(manager.root)
                    if rel.parts and rel.parts[0]=='backups':continue
                    if rel.as_posix()=='master.key':continue
                    if not include_logs and rel.as_posix().startswith('runtime/') and rel.suffix=='.jsonl':continue
                    z.write(f,rel.as_posix());count+=1
            return {'status':'SUCCESS','path':str(p.relative_to(manager.root)),'files':count,'bytes':p.stat().st_size,'security_note':'master.key is intentionally excluded; encrypted secrets require the existing local master key or configured NOTSIP_MASTER_KEY for recovery'}
        manager.create=create_safe;manager._notsip_secure_backup_create=True
    def restore_safe(name,confirm=False):
        if not confirm:raise PermissionError('restore requires explicit confirmation')
        archive=(manager.dir/name).resolve()
        if manager.dir not in archive.parents:raise ValueError('invalid backup path')
        with zipfile.ZipFile(archive) as z:
            members=manager._safe_members(z)
            if z.testzip() is not None:raise ValueError('backup archive is corrupt')
            stage=Path(tempfile.mkdtemp(prefix='notsip-restore-',dir=manager.root.parent));rollback=Path(tempfile.mkdtemp(prefix='notsip-rollback-',dir=manager.root.parent));changes=[]
            try:
                for info in members:
                    target=(stage/info.filename).resolve()
                    if stage not in target.parents and target!=stage:raise ValueError('backup contains unsafe archive path')
                    if info.is_dir():target.mkdir(parents=True,exist_ok=True);continue
                    target.parent.mkdir(parents=True,exist_ok=True)
                    with z.open(info) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst)
                for item in stage.iterdir():
                    target=(manager.root/item.name).resolve()
                    if manager.root not in target.parents:raise ValueError('invalid restore target')
                    backup_target=rollback/item.name;existed=target.exists();changes.append((target,backup_target,existed))
                    if existed:shutil.move(str(target),str(backup_target))
                    try:shutil.move(str(item),str(target))
                    except Exception:
                        if existed and backup_target.exists():shutil.move(str(backup_target),str(target))
                        raise
                return {'status':'SUCCESS','restored':name,'restart_required':True,'rollback_snapshot':str(rollback.relative_to(manager.root.parent))}
            except Exception:
                for target,backup_target,existed in reversed(changes):
                    try:
                        if target.exists():shutil.rmtree(target) if target.is_dir() else target.unlink()
                        if existed and backup_target.exists():
                            target.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(backup_target),str(target))
                    except Exception:pass
                raise
            finally:shutil.rmtree(stage,ignore_errors=True);shutil.rmtree(rollback,ignore_errors=True)
    manager.restore=restore_safe
    return manager
