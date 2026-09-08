$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

# The packaged updater and Python UpdateManager are the only supported update paths.
# This script never copies an arbitrary executable over an installed NOTSIP binary.
$python = Get-Command python.exe -ErrorAction SilentlyContinue
if(-not $python){ throw 'Python is required to invoke the NOTSIP trusted updater. Use the packaged NOTSIP updater for frozen installations.' }
$sourceRoot=(Get-Location).Path
$env:PYTHONPATH=Join-Path $sourceRoot 'src'
$code=@'
import asyncio
import json
from pathlib import Path
from notsip.config import settings
from notsip.updater import UpdateManager

async def main():
    if not settings.github_update_enabled:
        raise RuntimeError('automatic updates are disabled')
    manager=UpdateManager(Path(settings.data_dir),settings)
    result=await manager.download_release_asset('NOTSIP.exe')
    print(json.dumps(result,sort_keys=True))

asyncio.run(main())
'@
& $python.Source -c $code
if($LASTEXITCODE -ne 0){ throw "NOTSIP trusted updater failed with exit code $LASTEXITCODE" }
