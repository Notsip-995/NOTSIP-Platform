import asyncio
from notsip.account_store import AccountStore
from notsip.oauth_services import OAuthService
from notsip.security import SecretStore


def test_google_revocation_fails_closed_when_multiple_accounts_share_project(tmp_path):
    secrets=SecretStore(tmp_path);accounts=AccountStore(secrets)
    a=accounts.upsert('google','subject-a','a@example.com')
    b=accounts.upsert('google','subject-b','b@example.com')
    accounts.save_tokens(a['id'],{'access_token':'token-a','refresh_token':'refresh-a'})
    accounts.save_tokens(b['id'],{'access_token':'token-b','refresh_token':'refresh-b'})
    outcome=asyncio.run(OAuthService(secrets,accounts).revoke('google',a['id']))
    assert outcome['status']=='PROVIDER_REVOCATION_BLOCKED_MULTI_ACCOUNT'
    assert accounts.get(a['id'])['status']=='CONNECTED'
    assert accounts.tokens(b['id'])['access_token']=='token-b'


def test_microsoft_revocation_never_claims_provider_success_without_supported_operation(tmp_path):
    secrets=SecretStore(tmp_path);accounts=AccountStore(secrets)
    a=accounts.upsert('microsoft','subject-a','a@example.com')
    accounts.save_tokens(a['id'],{'access_token':'token-a','refresh_token':'refresh-a'})
    outcome=asyncio.run(OAuthService(secrets,accounts).revoke('microsoft',a['id']))
    assert outcome['status']=='PROVIDER_REVOCATION_UNAVAILABLE'
    assert accounts.get(a['id'])['status']=='CONNECTED'
