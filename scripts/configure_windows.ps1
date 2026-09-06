$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$envFile='.env'; $values=@{}
if(Test-Path $envFile){Get-Content $envFile | ForEach-Object {if($_ -match '^([A-Z0-9_]+)=(.*)$'){$values[$matches[1]]=$matches[2]}}}
function Ask($name,$prompt,$secret=$false,$default=''){
  $existing=if($values.ContainsKey($name)){$values[$name]}else{$default}
  if($secret){$v=Read-Host "$prompt" -AsSecureString;$b=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($v);try{$plain=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($b)}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b)}}else{$suffix=if($existing){" [$existing]"}else{''};$plain=Read-Host "$prompt$suffix";if(-not $plain){$plain=$existing}}
  $values[$name]=$plain
}
Write-Host '=== NOTSIP first-run configuration ===' -ForegroundColor Cyan
Write-Host 'Everything here is optional except the choices you actually want enabled. Secrets are hidden.'
Ask 'NOTSIP_HOST' 'Bind host' $false '127.0.0.1'; Ask 'NOTSIP_PORT' 'Port' $false '8765'; Ask 'NOTSIP_LOCAL_TIMEZONE' 'Local timezone' $false 'Africa/Kigali'
Ask 'NOTSIP_API_KEY' 'Control-plane API key' $true; Ask 'NOTSIP_AUTH_MODE' 'Authentication mode (api_key/oidc)' $false 'api_key'; Ask 'NOTSIP_SESSION_TTL' 'Session lifetime seconds' $false '43200'
Ask 'NOTSIP_AUTONOMY_LEVEL' 'Autonomy level 0-4' $false '2'; Ask 'NOTSIP_SELF_MODIFY_ENABLED' 'Enable controlled self-maintenance true/false' $false 'false'
Ask 'NOTSIP_LLM_BASE_URL' 'Primary OpenAI-compatible base URL' $false; Ask 'NOTSIP_LLM_MODEL' 'Primary model' $false; Ask 'NOTSIP_LLM_API_KEY' 'Primary model API key' $true
Ask 'NOTSIP_FALLBACK_LLM_BASE_URL' 'Fallback model base URL' $false; Ask 'NOTSIP_FALLBACK_LLM_MODEL' 'Fallback model' $false; Ask 'NOTSIP_FALLBACK_LLM_API_KEY' 'Fallback model API key' $true
Ask 'NOTSIP_STT_BASE_URL' 'Speech-to-text OpenAI-compatible base URL' $false; Ask 'NOTSIP_STT_MODEL' 'STT model' $false; Ask 'NOTSIP_STT_API_KEY' 'STT API key' $true; Ask 'NOTSIP_STT_LANGUAGE' 'Preferred STT language' $false
Ask 'NOTSIP_TTS_BASE_URL' 'Text-to-speech OpenAI-compatible base URL' $false; Ask 'NOTSIP_TTS_MODEL' 'TTS model' $false; Ask 'NOTSIP_TTS_API_KEY' 'TTS API key' $true; Ask 'NOTSIP_TTS_VOICE' 'TTS voice' $false 'alloy'; Ask 'NOTSIP_TTS_FORMAT' 'TTS audio format' $false 'mp3'
Ask 'NOTSIP_VISION_ENABLED' 'Enable visual perception true/false' $false 'true'; Ask 'NOTSIP_PERCEPTION_ENABLED' 'Enable continuous perception pipeline true/false' $false 'true'; Ask 'NOTSIP_PERCEPTION_INTERVAL' 'Perception interval seconds' $false '10'
Ask 'NOTSIP_BRAVE_API_KEY' 'Brave Search API key' $true; Ask 'NOTSIP_BROWSER_ENABLED' 'Enable browser extraction true/false' $false 'true'
Ask 'NOTSIP_SMTP_HOST' 'SMTP host' $false; Ask 'NOTSIP_SMTP_PORT' 'SMTP port' $false '587'; Ask 'NOTSIP_IMAP_HOST' 'IMAP host' $false; Ask 'NOTSIP_EMAIL_USERNAME' 'Email username' $false; Ask 'NOTSIP_EMAIL_PASSWORD' 'Email/app password' $true
Ask 'NOTSIP_OIDC_PROVIDER' 'OIDC provider (google/microsoft/generic)' $false 'generic'; Ask 'NOTSIP_OIDC_ISSUER' 'OIDC issuer URL' $false; Ask 'NOTSIP_OIDC_CLIENT_ID' 'OIDC client ID' $false; Ask 'NOTSIP_OIDC_CLIENT_SECRET' 'OIDC client secret' $true; Ask 'NOTSIP_OIDC_REDIRECT_URI' 'OIDC redirect URI' $false 'http://127.0.0.1:8765/api/oauth/callback'; Ask 'NOTSIP_OIDC_SCOPES' 'OIDC scopes' $false 'openid profile email'
Ask 'NOTSIP_OAUTH_AUTHORIZE_URL' 'External OAuth authorize URL (optional)' $false; Ask 'NOTSIP_OAUTH_TOKEN_URL' 'External OAuth token URL (optional)' $false; Ask 'NOTSIP_OAUTH_CLIENT_ID' 'External OAuth client ID (optional)' $false; Ask 'NOTSIP_OAUTH_CLIENT_SECRET' 'External OAuth client secret (optional)' $true; Ask 'NOTSIP_OAUTH_REDIRECT_URI' 'External OAuth redirect URI (optional)' $false
Ask 'NOTSIP_ANDROID_POLL_SECONDS' 'Android command polling seconds' $false '3'; Ask 'NOTSIP_NODE_LEASE_SECONDS' 'Federated node lease seconds' $false '90'; Ask 'NOTSIP_NODE_SHARED_SECRET' 'Node federation shared secret' $true
Ask 'NOTSIP_EVENT_HMAC_SECRET' 'Event HMAC secret' $true; Ask 'NOTSIP_PAIRING_SECRET' 'Android pairing secret' $true
@($values.GetEnumerator()|Sort-Object Name|ForEach-Object{"$($_.Key)=$($_.Value)"})|Set-Content $envFile -Encoding UTF8
Write-Host 'Configuration saved. .env is excluded from Git.' -ForegroundColor Green
