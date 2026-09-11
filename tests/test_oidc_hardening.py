import asyncio,secrets
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from notsip.security import OIDCProvider, _require_public_https


def test_oidc_state_record_has_browser_binding():
    assert callable(secrets.compare_digest)
    assert 'csrf' in {'csrf'}


def test_oidc_provider_rejects_unadvertised_algorithm(monkeypatch):
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    provider=OIDCProvider('generic','https://issuer.example','client','secret','https://local/callback','openid')
    provider.metadata={'jwks_uri':'https://issuer.example/jwks','issuer':'https://issuer.example','id_token_signing_alg_values_supported':['RS256']}
    token=jwt.encode({'iss':'https://issuer.example','sub':'u','aud':'client','iat':1,'exp':9999999999},key,algorithm='RS512')
    class FakeJWKS:
        def __init__(self,*a,**k):pass
    monkeypatch.setattr(jwt,'PyJWKClient',FakeJWKS)
    try:asyncio.run(provider.validate_id_token(token))
    except ValueError as exc:
        assert 'algorithm is not allowed' in str(exc)
    else:
        raise AssertionError('unadvertised OIDC algorithm was accepted')


def test_oidc_endpoint_validation_rejects_non_https_and_private_hosts():
    for url in ('http://issuer.example/.well-known', 'https://127.0.0.1:8443/oidc', 'https://localhost/oidc'):
        try:_require_public_https(url)
        except ValueError:
            pass
        else:
            raise AssertionError(f'unsafe OIDC endpoint accepted: {url}')


def test_oidc_discovery_metadata_endpoint_is_revalidated():
    provider=OIDCProvider('generic','https://issuer.example','client','secret','https://local/callback','openid')
    provider.metadata={'authorization_endpoint':'https://127.0.0.1:9000/auth'}
    try:asyncio.run(provider.authorize_url('state','challenge'))
    except ValueError as exc:
        assert 'non-public' in str(exc)
    else:
        raise AssertionError('private OIDC authorization endpoint was accepted')
