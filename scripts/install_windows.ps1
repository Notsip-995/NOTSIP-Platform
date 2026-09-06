$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev,windows]"
.\.venv\Scripts\python.exe -m playwright install chromium
if(-not(Test-Path .env)){Copy-Item .env.example .env}
New-Item -ItemType Directory -Force data\workspace,data\screenshots,data\audio,data\perception,data\recovery | Out-Null
& .\scripts\configure_windows.ps1
Write-Host 'NOTSIP installation complete. Start with scripts\start_windows.ps1'
