def test_business_admin_token_is_secret_and_high_risk():
    from notsip import app
    from notsip.product_layer import ConfigStore
    assert 'business_admin_token' in app.CONFIG_SECRET_NAMES
    assert 'business_admin_token' in app.CONFIG_HIGH_RISK
    assert 'business_admin_token' in ConfigStore.SECRET_NAMES


def test_business_admin_token_is_not_serialized_by_config_store(tmp_path):
    from notsip.product_layer import ConfigStore
    store=ConfigStore(tmp_path)
    store.save({'business_admin_url':'https://example.com','business_admin_token':'super-secret'})
    text=store.path.read_text(encoding='utf-8')
    assert 'super-secret' not in text
    assert 'business_admin_url' in text
