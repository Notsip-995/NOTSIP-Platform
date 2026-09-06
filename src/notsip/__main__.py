from __future__ import annotations
import os, socket, sys, webbrowser
from pathlib import Path
import uvicorn
from notsip.config import settings
from notsip.core_runtime import app
from notsip.product_layer import ProcessGuard, resource_root, choose_free_port

def _is_notsip_listener(host:str,port:int)->bool:
    import urllib.request
    try:
        with urllib.request.urlopen(f'http://{host}:{port}/api/health',timeout=.8) as r:
            return r.status==200 and 'NOTSIP' in r.read().decode('utf-8','replace')
    except Exception:return False

def _port_in_use(host:str,port:int)->bool:
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:s.settimeout(.25);return s.connect_ex((host,port))==0

def _select_port(host:str,configured:int)->int:
    if not _port_in_use(host,configured):return configured
    if _is_notsip_listener(host,configured):
        print(f'NOTSIP is already running at http://{host}:{configured}/');return 0
    return choose_free_port(host,configured+1,20)

def _open_browser(url:str):
    try:webbrowser.open(url)
    except Exception:pass

def main()->None:
    frozen=getattr(sys,'_MEIPASS',None)
    import notsip.runtime_prod as runtime_prod
    if frozen:
        runtime_prod.ROOT=Path(frozen)
        if hasattr(runtime_prod,'maint'):runtime_prod.maint.root=Path(os.environ.get('NOTSIP_REPO_ROOT',Path.cwd())).resolve()
    host=settings.host;port=_select_port(host,settings.port)
    if port==0:return
    settings.port=port;os.environ['NOTSIP_EFFECTIVE_PORT']=str(port)
    guard=ProcessGuard(root=Path(settings.data_dir))
    if not guard.acquire():
        url=f'http://{host}:{port}/';print(f'NOTSIP is already running; opening {url}');_open_browser(url);return
    try:
        url=f'http://{host}:{port}/'
        print(f'NOTSIP listening at {url}')
        if settings.open_browser:_open_browser(url)
        uvicorn.run(app,host=host,port=port,log_level=settings.log_level.lower())
    finally:guard.release()

if __name__=='__main__':main()
