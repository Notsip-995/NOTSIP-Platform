$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$envFile='.env'
$values=@{}
if(Test-Path $envFile){Get-Content $envFile | ForEach-Object { if($_ -match '^([A-Z0-9_]+)=(.*)$'){ $values[$matches[1]]=$matches[2] } }}
function Ask($name,$prompt,$secret=$false,$default=''){
  $existing=if($values.ContainsKey($name)){$values[$name]}else{$default}
  if($existing -and $name -notmatch 'PASSWORD|API_KEY|SECRET'){ $default=$existing }
  if($secret){$v=Read-Host "$prompt" -AsSecureString; $bstr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($v); try{$plain=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)}} else {$suffix=if($default){" [$default]"}else{''};$plain=Read-Host "$prompt$suffix";if(-not $plain){$plain=$default}}
  $values[$name]=$plain
}
Write-Host ''
Write-Host '=== NOTSIP first-run configuration ===' -ForegroundColor Cyan
Write-Host 'Press Enter to keep an existing/default value. Secret fields are not displayed.'
Write-Host ''
Ask 'NOTSIP_API_KEY' 'Control-plane API key (recommended)' $true
Ask 'NOTSIP_AUTONOMY_LEVEL' 'Autonomy level 0-4' $false '2'
Ask 'NOTSIP_SELF_MODIFY_ENABLED' 'Allow controlled self-maintenance? true/false' $false 'false'
Ask 'NOTSIP_LLM_BASE_URL' 'Primary OpenAI-compatible base URL' $false
Ask 'NOTSIP_LLM_MODEL' 'Primary model name' $false
Ask 'NOTSIP_LLM_API_KEY' 'Primary model API key' $true
Ask 'NOTSIP_FALLBACK_LLM_BASE_URL' 'Fallback model base URL' $false
Ask 'NOTSIP_FALLBACK_LLM_MODEL' 'Fallback model name' $false
Ask 'NOTSIP_FALLBACK_LLM_API_KEY' 'Fallback model API key' $true
Ask 'NOTSIP_BRAVE_API_KEY' 'Brave Search API key' $true
Ask 'NOTSIP_SMTP_HOST' 'SMTP host' $false
Ask 'NOTSIP_SMTP_PORT' 'SMTP port' $false '587'
Ask 'NOTSIP_IMAP_HOST' 'IMAP host' $false
Ask 'NOTSIP_EMAIL_USERNAME' 'Email username' $false
Ask 'NOTSIP_EMAIL_PASSWORD' 'Email password/app password' $true
Ask 'NOTSIP_OAUTH_AUTHORIZE_URL' 'OAuth authorize URL' $false
Ask 'NOTSIP_OAUTH_TOKEN_URL' 'OAuth token URL' $false
Ask 'NOTSIP_OAUTH_CLIENT_ID' 'OAuth client ID' $false
Ask 'NOTSIP_OAUTH_CLIENT_SECRET' 'OAuth client secret' $true
Ask 'NOTSIP_OAUTH_REDIRECT_URI' 'OAuth redirect URI' $false 'http://127.0.0.1:8765/api/oauth/callback'
Ask 'NOTSIP_OAUTH_SCOPES' 'OAuth scopes' $false
Ask 'NOTSIP_EVENT_HMAC_SECRET' 'External event HMAC secret' $true
Ask 'NOTSIP_PAIRING_SECRET' 'Android pairing secret' $true
@($values.GetEnumerator() | Sort-Object Name | ForEach-Object { "$($_.Key)=$($_.Value)" }) | Set-Content $envFile -Encoding UTF8
Write-Host ''
Write-Host 'Configuration saved to .env (excluded from Git).' -ForegroundColor Green
