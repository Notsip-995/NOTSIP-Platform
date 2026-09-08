from pathlib import Path


def test_database_url_is_classified_as_secret_in_all_config_layers():
    config=Path('src/notsip/config.py').read_text(encoding='utf-8')
    hardening=Path('src/notsip/config_hardening.py').read_text(encoding='utf-8')
    assert "'database_url'" in config.split('SECRET_FIELDS=',1)[1].split('\n',1)[0]
    assert "'database_url'" in hardening.split('SECRET_NAMES=',1)[1].split('\n',1)[0]
    assert "safe['database_url']='[configured]'" in hardening
