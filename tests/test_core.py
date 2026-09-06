from notsip.store import Store
from notsip.tools import calc,Workspace
from notsip.policy import Policy

def test_calc(): assert calc('12.5*8')==100

def test_policy(): assert Policy(2).decide(0).allowed and not Policy(2).decide(2).allowed

def test_memory(tmp_path):
 s=Store(tmp_path);s.remember('u','semantic','Atlas workstation',.9);assert s.memories('u','Atlas')[0]['content']=='Atlas workstation'

def test_workspace_escape(tmp_path):
 w=Workspace(tmp_path)
 try:w.read('../bad')
 except PermissionError:pass
 else:raise AssertionError

def test_pair(tmp_path):
 from notsip.android_bridge import Pairing
 s=Store(tmp_path);p=Pairing(s);t=p.consume(p.create_code(),'phone','Tecno','android');assert s.device_token_valid('phone',t)
