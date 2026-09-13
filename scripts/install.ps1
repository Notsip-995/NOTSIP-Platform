# NOTSIP one-shot installer launcher (Windows PowerShell)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python 3.12+ is required. Install it from https://www.python.org/downloads/ and re-run.'
}
python scripts\install.py
if ($LASTEXITCODE -ne 0) { throw 'NOTSIP installer failed (see messages above).' }