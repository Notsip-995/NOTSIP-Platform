$ErrorActionPreference='Stop'
$exe=(Resolve-Path (Join-Path $PSScriptRoot '..\dist\NOTSIP.exe') -ErrorAction Stop).Path
$startup=[Environment]::GetFolderPath('Startup')
$shortcut=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $startup 'NOTSIP.lnk'))
$shortcut.TargetPath=$exe;$shortcut.WorkingDirectory=Split-Path $exe;$shortcut.Arguments='';$shortcut.Save()
Write-Host 'NOTSIP startup shortcut registered.' -ForegroundColor Green
