import smtplib
from notsip.connectors import Email
from notsip.config import settings
import pytest


def test_authenticated_smtp_requires_tls_on_port_25(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'email_username','user@example.com')
    monkeypatch.setattr(settings,'email_password','secret')
    monkeypatch.setattr(settings,'smtp_host','smtp.example.com')
    monkeypatch.setattr(settings,'smtp_port',25)
    monkeypatch.setattr(settings,'imap_host','')
    class FakeSMTP:
        def __init__(self,*args,**kwargs): self.tls=False
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def starttls(self,**kwargs): self.tls=True
        def login(self,*args):
            assert self.tls is True
        def send_message(self,*args): return None
    monkeypatch.setattr(smtplib,'SMTP',FakeSMTP)
    result=Email().send('dest@example.com','subject','body')
    assert result['transport_tls'] is True


def test_authenticated_smtp_failure_to_start_tls_does_not_login(monkeypatch):
    monkeypatch.setattr(settings,'email_username','user@example.com')
    monkeypatch.setattr(settings,'email_password','secret')
    monkeypatch.setattr(settings,'smtp_host','smtp.example.com')
    monkeypatch.setattr(settings,'smtp_port',25)
    monkeypatch.setattr(settings,'imap_host','')
    class FakeSMTP:
        def __init__(self,*args,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def starttls(self,**kwargs): raise smtplib.SMTPException('TLS unavailable')
        def login(self,*args): raise AssertionError('credentials must not be sent before TLS')
    monkeypatch.setattr(smtplib,'SMTP',FakeSMTP)
    with pytest.raises(smtplib.SMTPException,match='TLS unavailable'):
        Email().send('dest@example.com','subject','body')
