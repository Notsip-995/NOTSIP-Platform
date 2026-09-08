$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

# The runtime updater is the single authoritative self-update path. It requires
# GitHub release provenance, SHA-256 verification, and Windows Authenticode
# publisher verification before replacing the installed executable.
$python = (Get-Command python.exe -ErrorAction SilentlyContinue)
if(-not $python){ throw 'Python is required to invoke the NOTSIP signed updater. Use the packaged NOTSIP updater for frozen installs.' }

$sourceRoot = (Get-Location).Path
$code = @'
import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace
from notsip.config import settings
from notsip.updater import UpdateManager

async def main():
    if not settings.github_update_enabled:
        raise RuntimeError('automatic updates are disabled')
    manager = UpdateManager(Path(settings.data_dir), settings)
    release = await manager.check()
    if not release.get('available'):
        print(json.dumps({'status':'NO_UPDATE','release':release}, sort_keys=True))
        return
    assets = release.get('assets') or []
    exe = next((a for a in assets if str(a.get('name','')).lower() == 'notsip.exe'), None)
    if exe is None:
        raise RuntimeError('trusted latest release does not contain NOTSIP.exe')
    # Release download requires an expected SHA-256 supplied by the trusted
    # release metadata; do not permit arbitrary local EXEs or digests here.
    sha_url = exe.get('sha256_url')
    if not sha_url:
        raise RuntimeError('trusted release does not publish a SHA-256 manifest for NOTSIP.exe')
    import httpx
    token = os.getenv('NOTSIP_GITHUB_TOKEN','')
    headers={'Accept':'text/plain'}
    if token: headers['Authorization']='Bearer '+token
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        current=sha_url
        for _ in range(6):
            h=dict(headers)
            from urllib.parse import urlparse,urljoin
            if urlparse(current).netloc.lower()!='github.com': h.pop('Authorization',None)
            response=await client.get(current,headers=h)
            if response.is_redirect:
                dest=urljoin(current,response.headers.get('location',''))
                if not manager._trusted_redirect(dest): raise RuntimeError('untrusted SHA-256 manifest redirect')
                current=dest; continue
            response.raise_for_status(); manifest=response.text; break
        else: raise RuntimeError('too many SHA-256 manifest redirects')
    digest = manifest.strip().split()[0].lower()
    if len(digest)!=64: raise RuntimeError('invalid SHA-256 manifest')
    result = await manager.download(exe['url'], digest)
    print(json.dumps(result, sort_keys=True))

asyncio.run(main())
'@

$env:PYTHONPATH = Join-Path $sourceRoot 'src'
& $python.Source -c $code
if($LASTEXITCODE -ne 0){ throw "NOTSIP trusted updater failed with exit code $LASTEXITCODE" }
