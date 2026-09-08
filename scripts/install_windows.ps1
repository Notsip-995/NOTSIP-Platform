$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if(-not(Test-Path .venv)){py -3.12 -m venv .venv}
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev,windows]"
.\.venv\Scripts\python.exe -m playwright install chromium
# Do not create a real .env from .env.example. The graphical Setup is the source of truth.
New-Item -ItemType Directory -Force data\workspace,data\screenshots,data\audio,data\perception,data\recovery,data\runtime,data\backups | Out-Null
Write-Host 'Starting NOTSIP first-run setup...' -ForegroundColor Cyan
Start-Process -FilePath '.\.venv\Scripts\python.exe' -ArgumentList '-m','notsip' -WorkingDirectory (Get-Location)
$lockCandidates=@((Join-Path (Get-Location) 'data\runtime\instance.lock'),(Join-Path $env:LOCALAPPDATA 'NOTSIP\data\runtime\instance.lock'))
$url='http://127.0.0.1:8765/setup'
for($i=0;$i -lt 30;$i++){
  foreach($path in $lockCandidates){
    if(Test-Path $path){try{$lock=Get-Content -Raw -Path $path|ConvertFrom-Json;if($lock.host -and $lock.port){$url="http://$($lock.host):$($lock.port)/setup";break}}catch{}}
  }
  try{Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 1|Out-Null;break}catch{Start-Sleep -Milliseconds 500}
}
Start-Process $url
Write-Host "NOTSIP is running. Complete setup at $url, then use the console at the same host/port." -ForegroundColor Green
