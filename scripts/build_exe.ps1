$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if(-not(Test-Path .venv)){py -3.12 -m venv .venv}
.\.venv\Scripts\python.exe -m pip install -e ".[windows]"
.\.venv\Scripts\python.exe -m pip install pyinstaller
Remove-Item -Recurse -Force build,dist -ErrorAction SilentlyContinue
.\.venv\Scripts\pyinstaller.exe --noconfirm --clean --onefile --name NOTSIP --paths src --add-data "ui.html;." src\notsip\__main__.py
Write-Host "Built dist\NOTSIP.exe" -ForegroundColor Green
