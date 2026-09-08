param([ValidateSet('start','stop','restart','status','setup')][string]$Action='start')
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$python=Join-Path (Get-Location) '.venv\Scripts\python.exe'
function Get-NotsipConfig {
  $candidates=@((Join-Path (Get-Location) 'data\config.json'),(Join-Path $env:LOCALAPPDATA 'NOTSIP\data\config.json'))
  foreach($path in $candidates){if(Test-Path $path){try{return (Get-Content -Raw -Path $path | ConvertFrom-Json)}catch{}}}
  return $null
}
function Get-NotsipUrl {
  $lockCandidates=@((Join-Path (Get-Location) 'data\runtime\instance.lock'),(Join-Path $env:LOCALAPPDATA 'NOTSIP\data\runtime\instance.lock'))
  foreach($path in $lockCandidates){
    if(Test-Path $path){
      try{
        $lock=Get-Content -Raw -Path $path | ConvertFrom-Json
        if($lock.host -and $lock.port){return "http://$($lock.host):$($lock.port)"}
      }catch{}
    }
  }
  $cfg=Get-NotsipConfig;$host='127.0.0.1';$port=8765
  if($cfg -and $cfg.settings){if($cfg.settings.host){$host=[string]$cfg.settings.host};if($cfg.settings.port){$port=[int]$cfg.settings.port}}
  return "http://$host`:$port"
}
function Get-Notsip { Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'notsip' -or $_.Name -eq 'NOTSIP.exe' } }
switch($Action){
  'status' { $url=Get-NotsipUrl;Get-Notsip|Select-Object ProcessId,Name,CommandLine;try{Invoke-WebRequest "$url/api/health" -UseBasicParsing -TimeoutSec 2|Select-Object StatusCode}catch{Write-Host "NOTSIP HTTP endpoint is not responding at $url."};break }
  'stop' { Get-Notsip|ForEach-Object{Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue};break }
  'restart' { & $PSCommandPath stop;Start-Sleep 1;& $PSCommandPath start;break }
  'setup' { Start-Process "$(Get-NotsipUrl)/setup";break }
  default { if(Test-Path 'dist\NOTSIP.exe'){Start-Process '.\dist\NOTSIP.exe'}elseif(Test-Path $python){Start-Process $python -ArgumentList '-m','notsip' -WorkingDirectory (Get-Location)}else{throw 'NOTSIP is not installed. Run scripts\install_windows.ps1.'} }
}
