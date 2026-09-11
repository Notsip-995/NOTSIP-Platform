from __future__ import annotations
import os, shutil, subprocess
from pathlib import Path


def _authenticode_valid(path: Path, expected_thumbprint: str) -> bool:
    if os.name != 'nt' or not expected_thumbprint:
        return False
    command = "$s=Get-AuthenticodeSignature -FilePath $args[0]; [pscustomobject]@{Status=[string]$s.Status;Thumbprint=[string]$s.SignerCertificate.Thumbprint}|ConvertTo-Json -Compress"
    try:
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command, '--', str(path)],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return False
        import json
        data = json.loads(result.stdout)
        thumbprint = str(data.get('Thumbprint', '')).replace(' ', '').upper()
        return data.get('Status') == 'Valid' and thumbprint == expected_thumbprint.replace(' ', '').upper()
    except Exception:
        return False


def reconcile_frozen_update(root: Path, current_exe: Path, publisher_thumbprint: str) -> dict:
    """Recover from a power-loss/interruption during signed self-update.

    An update backup is retained until a later successful cleanup. If the
    current executable is not Authenticode-valid for the configured publisher,
    restore the newest pre-update backup before importing the application.
    """
    updates = (Path(root) / 'updates').resolve()
    updates.mkdir(parents=True, exist_ok=True)
    current = Path(current_exe).resolve()
    backups = sorted(updates.glob('previous-*.exe'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not backups:
        return {'status': 'NO_PENDING_UPDATE', 'recovered': False}
    if _authenticode_valid(current, publisher_thumbprint):
        return {'status': 'CURRENT_BINARY_VALID', 'recovered': False, 'pending_backups': len(backups)}
    for backup in backups:
        if not _authenticode_valid(backup, publisher_thumbprint):
            continue
        temp = current.with_suffix(current.suffix + '.recovery.tmp')
        try:
            shutil.copy2(backup, temp)
            os.replace(temp, current)
            for helper in updates.glob('apply-*.ps1'):
                try: helper.unlink()
                except OSError: pass
            return {'status': 'ROLLED_BACK', 'recovered': True, 'backup': str(backup)}
        except Exception:
            try: temp.unlink()
            except OSError: pass
            continue
    return {'status': 'RECOVERY_UNAVAILABLE', 'recovered': False, 'reason': 'no valid signed rollback binary was available'}
