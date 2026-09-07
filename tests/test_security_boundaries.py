import json
from pathlib import Path
from notsip.connectors import _public_host
from notsip.product_layer import ConfigStore
from notsip.security import SecretStore


def test_public_host_rejects_private_and_loopback_literals():
    for host in ('127.0.0.1','localhost','10.0.0.1','192.168.1.1','169.254.169.254','::1'):
        assert _public_host(host) is False


def test_config_store_never_persists_protected_database_url(tmp_path):
    c=ConfigStore(tmp_path)
    c.save({'host':'127.0.0.1','database_url':'postgresql://user:password@example/db'})
    raw=json.loads((Path(tmp_path)/'config.json').read_text())
    assert 'database_url' not in raw['settings']


def test_secret_store_database_url_roundtrip(tmp_path):
    s=SecretStore(tmp_path)
    s.set('NOTSIP_DATABASE_URL','postgresql://user:password@example/db')
    assert s.get('NOTSIP_DATABASE_URL')=='postgresql://user:password@example/db'
    s.set('NOTSIP_DATABASE_URL','')
    assert s.get('NOTSIP_DATABASE_URL') is None
