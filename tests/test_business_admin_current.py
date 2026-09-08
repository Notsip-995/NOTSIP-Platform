from pathlib import Path


def test_business_admin_requires_token_and_explicit_success():
    text=Path('src/notsip/business_admin.py').read_text(encoding='utf-8')
    assert "return bool(self.base_url and self.token)" in text
    assert "if 'success' not in data:return {'status':'UNKNOWN'" in text
    assert "'provider_success_field_present':True" in text
