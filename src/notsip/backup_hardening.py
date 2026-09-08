from __future__ import annotations
import shutil,tempfile,uuid,zipfile
from pathlib import Path

def install(manager):
    def restore_safe(name,confirm=False):
        if not confirm:raise PermissionError('restore requires explicit confirmation')
        archive=(manager.dir/name).resolve()
        if manager.dir not in archive.parents:raise ValueError('invalid backup path')
        with zipfile.ZipFile(archive) as z:
            members=manager._safe_members(z)
            if z.testzip() is not None:raise ValueError('backup archive is corrupt')
            stage=Path(tempfile.mkdtemp(prefix='notsip-restore-',dir=manager.root.parent))
            rollback=Path(tempfile.mkdtemp(prefix='notsip-rollback-',dir=manager.root.parent))
            moved=[]
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
                    backup_target=rollback/item.name
                    if target.exists():
                        backup_target.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(target),str(backup_target))
                    shutil.move(str(item),str(target));moved.append((target,backup_target))
                return {'status':'SUCCESS','restored':name,'restart_required':True,'rollback_snapshot':str(rollback.relative_to(manager.root.parent))}
            except Exception:
                for target,backup_target in reversed(moved):
                    try:
                        if target.exists():shutil.rmtree(target) if target.is_dir() else target.unlink()
                        if backup_target.exists():
                            target.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(backup_target),str(target))
                    except Exception:pass
                raise
            finally:
                shutil.rmtree(stage,ignore_errors=True)
                # Successful restores retain rollback material until the next explicit cleanup/maintenance pass.
    manager.restore=restore_safe
    return manager
