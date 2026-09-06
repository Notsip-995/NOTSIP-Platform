$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if(-not(Test-Path .venv)){py -3.12 -m venv .venv}
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev,windows]"
.\.venv\Scripts\python.exe -m playwright install chromium
if(-not(Test-Path .env)){Copy-Item .env.example .env}
New-Item -ItemType Directory -Force data\workspace,data\screenshots,data\audio,data\perception,data\recovery,data\runtime,data\backups | Out-Null
Write-Host 'Starting NOTSIP first-run setup at http://127.0.0.1:8765/setup ...' -ForegroundColor Cyan
Start-Process -FilePath '.\.venv\Scripts\python.exe' -ArgumentList '-m','notsip' -WorkingDirectory (Get-Location)
Start-Sleep -Seconds 3
Start-Process 'http://127.0.0.1:8765/setup'
Write-Host 'NOTSIP is running. Complete setup in the browser, then use http://127.0.0.1:8765/.' -ForegroundColor Green
