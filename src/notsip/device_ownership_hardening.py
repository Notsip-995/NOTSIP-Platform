from __future__ import annotations
import json


def install(store):
    if getattr(store,'_device_ownership_hardened',False):
        return store
    original_owner=store.device_owner
    original_devices=store.devices

    def safe_owner(device_id):
        row=store.row('SELECT data FROM devices WHERE id=?',(device_id,)) if not getattr(store,'_backend',None) else store.row('SELECT data FROM devices WHERE id=%s',(device_id,))
        if not row:
            return None
        raw=row.get('data') or '{}'
        try:
            data=json.loads(raw)
        except (TypeError,json.JSONDecodeError):
            return None
        if not isinstance(data,dict):
            return None
        owner=data.get('owner')
        if owner is None:
            return 'primary-user'
        owner=str(owner).strip()
        return owner or None

    def safe_devices(owner=None):
        rows=original_devices(owner)
        safe=[]
        for row in rows:
            raw=row.get('data') or '{}'
            try:data=json.loads(raw)
            except (TypeError,json.JSONDecodeError):continue
            if not isinstance(data,dict):continue
            safe.append(row)
        return safe

    store.device_owner=safe_owner
    store.devices=safe_devices
    store._device_ownership_hardened=True
    return store
