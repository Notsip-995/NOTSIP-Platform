import subprocess
from pathlib import Path
from types import SimpleNamespace

from notsip.config import settings
from notsip.connectors import Email
from notsip.self_maintenance import SelfMaintenance


def test_smtp_465_uses_implicit_tls(monkeypatch):
    calls=[]
    class FakeSMTPSSL:
        def __init__(self,*args,**kwargs): calls.append(('SMTP_SSL',args,kwargs))
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def login(self,*args): calls.append(('login',args))
        def send_message(self,*args): calls.append(('send',args))
    class FailSMTP:
        def __init__(self,*args,**kwargs): raise AssertionError('plain SMTP must not be used for port 465')
    monkeypatch.setattr('notsip.connectors.smtplib.SMTP_SSL',FakeSMTPSSL)
    monkeypatch.setattr('notsip.connectors.smtplib.SMTP',FailSMTP)
    monkeypatch.setattr(settings,'email_username','user@example.com')
    monkeypatch.setattr(settings,'email_password','pw')
    monkeypatch.setattr(settings,'smtp_host','smtp.example.com')
    monkeypatch.setattr(settings,'smtp_port',465)
    mail=Email()
    result=mail.send('to@example.com','subject','body')
    assert result['status']=='SUCCESS'
    assert calls and calls[0][0]=='SMTP_SSL'


def test_self_maintenance_refuses_dirty_checkout(tmp_path, monkeypatch):
    repo=tmp_path/'repo';repo.mkdir()
    subprocess.run(['git','init'],cwd=repo,check=True,capture_output=True)
    (repo/'x.txt').write_text('existing\n',encoding='utf-8')
    subprocess.run(['git','add','x.txt'],cwd=repo,check=True,capture_output=True)
    subprocess.run(['git','-c','user.name=test','-c','user.email=test@example.com','commit','-m','init'],cwd=repo,check=True,capture_output=True)
    (repo/'x.txt').write_text('uncommitted\n',encoding='utf-8')
    monkeypatch.setattr(settings,'self_modify_enabled',True)
    maint=SelfMaintenance(repo)
    try:
        maint.apply_patch('', 'APPLY_SELF_CHANGE')
    except RuntimeError as exc:
        assert 'clean source workspace' in str(exc)
    else:
        raise AssertionError('dirty checkout must be rejected')
