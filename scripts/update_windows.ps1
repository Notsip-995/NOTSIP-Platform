$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$installRoot=Split-Path -Parent $MyInvocation.MyCommand.Path
$exe=Join-Path (Get-Location) 'dist\NOTSIP.exe'
if(-not(Test-Path $exe)){throw 'Run this from a source checkout and build the new NOTSIP.exe first.'}
$backup=Join-Path (Get-Location) ("data\runtime\updates\"+(Get-Date -Format yyyyMMdd-HHmmss))
New-Item -ItemType Directory -Force $backup | Out-Null
$old=Join-Path $backup 'NOTSIP.exe'
$installed=(Get-Command NOTSIP.exe -ErrorAction SilentlyContinue).Source
if($installed){Copy-Item $installed $old -Force}
Stop-Process -Name NOTSIP -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
$target=if($installed){$installed}else{Join-Path (Get-Location) 'NOTSIP.exe'}
Copy-Item $exe $target -Force
Start-Process $target
Start-Sleep -Seconds 3
try { $r=Invoke-WebRequest 'http://127.0.0.1:8765/api/health' -UseBasicParsing -TimeoutSec 5; if($r.StatusCode -ne 200){throw 'health check failed'}; Write-Host 'NOTSIP update verified.' -ForegroundColor Green }
catch {
  Stop-Process -Name NOTSIP -Force -ErrorAction SilentlyContinue
  if(Test-Path $old){Copy-Item $old $target -Force}
  throw "Update failed and previous executable was restored: $($_.Exception.Message)"
}
