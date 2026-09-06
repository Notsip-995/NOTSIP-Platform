from pathlib import Path
import re
from notsip.security import SecretStore

ROOT=Path(__file__).resolve().parents[1]; env=ROOT/'.env'; store=SecretStore((ROOT/'data').resolve())
SECRET_RE=re.compile(r'^(NOTSIP_(?:API_KEY|EVENT_HMAC_SECRET|PAIRING_SECRET|LLM_API_KEY|FALLBACK_LLM_API_KEY|STT_API_KEY|TTS_API_KEY|EMAIL_PASSWORD|OIDC_CLIENT_SECRET|OAUTH_CLIENT_SECRET|NODE_SHARED_SECRET))=(.*)$')
if not env.exists(): raise SystemExit(0)
lines=[]
for line in env.read_text(encoding='utf-8-sig').splitlines():
    m=SECRET_RE.match(line)
    if m and m.group(2): store.set(m.group(1),m.group(2)); lines.append(m.group(1)+'=')
    else: lines.append(line)
env.write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('Migrated configured secrets into the local encrypted secret store.')
