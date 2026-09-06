param([ValidateSet('start','stop','restart','status','setup')][string]$Action='start')
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$python=Join-Path (Get-Location) '.venv\Scripts\python.exe'
function Get-Notsip { Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'notsip' -or $_.Name -eq 'NOTSIP.exe' } }
switch($Action){
  'status' { Get-Notsip | Select-Object ProcessId,Name,CommandLine; try { Invoke-WebRequest 'http://127.0.0.1:8765/api/health' -UseBasicParsing -TimeoutSec 2 | Select-Object StatusCode } catch { Write-Host 'NOTSIP HTTP endpoint is not responding.' }; break }
  'stop' { Get-Notsip | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; break }
  'restart' { & $PSCommandPath stop; Start-Sleep 1; & $PSCommandPath start; break }
  'setup' { Start-Process 'http://127.0.0.1:8765/setup'; break }
  default {
    if(Test-Path 'dist\NOTSIP.exe') { Start-Process '.\dist\NOTSIP.exe' } elseif(Test-Path $python) { Start-Process $python -ArgumentList '-m','notsip' -WorkingDirectory (Get-Location) } else { throw 'NOTSIP is not installed. Run scripts\install_windows.ps1.' }
  }
}
