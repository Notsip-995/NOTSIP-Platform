from __future__ import annotations
import json,os,tempfile
from pathlib import Path

_FILES=('runtime/conversations.json',)
_PREFIX='user-profile-'

def capture(root):
    root=Path(root);items={}
    for rel in _FILES:
        p=root/rel
        if p.exists():
            data=json.loads(p.read_text(encoding='utf-8'));items[rel]=data
    for p in root.glob('user-profile-*.json'):
        if p.is_file():items[p.name]=json.loads(p.read_text(encoding='utf-8'))
    return items

def validate(files):
    if not isinstance(files,dict):raise ValueError('recovery durable user state must be an object')
    for name,data in files.items():
        if not (name=='runtime/conversations.json' or name.startswith(_PREFIX) and name.endswith('.json')):raise ValueError(f'unsupported recovery user-state file: {name}')
        if not isinstance(data,dict):raise ValueError(f'invalid recovery user-state payload: {name}')

def restore(root,files):
    validate(files);root=Path(root);root.mkdir(parents=True,exist_ok=True);backups=[];created=[]
    try:
        for name in files:
            target=(root/name).resolve()
            if root not in target.parents:raise ValueError('recovery user-state path escaped data directory')
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():
                fd,bpath=tempfile.mkstemp(prefix='notsip-recovery-backup-',dir=str(target.parent));os.close(fd);Path(bpath).write_bytes(target.read_bytes());backups.append((target,Path(bpath)))
            else:created.append(target)
            fd,tpath=tempfile.mkstemp(prefix='notsip-recovery-write-',dir=str(target.parent));os.close(fd);tmp=Path(tpath)
            tmp.write_text(json.dumps(files[name],sort_keys=True,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(target)
        return {'restored_files':sorted(files)}
    except Exception:
        for target,_ in backups:
            try:
                bak=next(b for t,b in backups if t==target)
                if bak.exists():bak.replace(target)
            except Exception:pass
        for target in created:
            try:target.unlink(missing_ok=True)
            except Exception:pass
        raise
    finally:
        for _,bak in backups:
            try:bak.unlink(missing_ok=True)
            except Exception:pass

def install_checkpoint_wrapper(recovery,root):
    original=recovery.checkpoint
    def checkpoint(state):
        payload=dict(state or {});payload['user_state']=capture(root);return original(payload)
    recovery.checkpoint=checkpoint
    return recovery
