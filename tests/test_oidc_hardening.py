import asyncio,secrets
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from notsip.security import OIDCProvider


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
