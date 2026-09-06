$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path .venv\Scripts\python.exe)) { throw 'Run scripts\install_windows.ps1 first.' }
.\.venv\Scripts\python.exe -m notsip
