from concurrent.futures import ThreadPoolExecutor
from notsip.security import SecretStore


def test_secret_store_preserves_concurrent_keys(tmp_path):
    store=SecretStore(tmp_path)
    def write(i):
        store.set(f'key-{i}',f'value-{i}')
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write,range(40)))
    data=store.load()
    assert len([k for k in data if k.startswith('key-')])==40
    for i in range(40):
        assert data[f'key-{i}']==f'value-{i}'
