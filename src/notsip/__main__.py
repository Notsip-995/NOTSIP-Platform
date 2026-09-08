from __future__ import annotations
import json, os, socket, sys, webbrowser
from pathlib import Path
import uvicorn
from notsip.config import settings
from notsip.product_layer import ProcessGuard


def _is_notsip_listener(host:str,port:int)->bool:
    import urllib.request
    try:
        with urllib.request.urlopen(f'http://{host}:{port}/',timeout=.8) as r:
            body=r.read().decode('utf-8','replace')
            return r.status==200 and 'NOTSIP' in body
    except Exception:
        return False


def _port_in_use(host:str,port:int)->bool:
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
        s.settimeout(.25)
        return s.connect_ex((host,port))==0


def _select_port(host:str,configured:int)->int:
    if not _port_in_use(host,configured):return configured
    if _is_notsip_listener(host,configured):
        print(f'NOTSIP is already running at http://{host}:{configured}/')
        return 0
    from notsip.product_layer import choose_free_port
    return choose_free_port(host,configured+1,20)


def _is_loopback_bind(host:str)->bool:
    return host.strip().lower() in {'127.0.0.1','localhost','::1'}


def _validate_bind_security(host:str)->None:
    if not settings.api_key and settings.auth_mode=='api_key' and not _is_loopback_bind(host):
        raise RuntimeError('refusing unauthenticated non-loopback bind; configure NOTSIP_API_KEY or OIDC before exposing NOTSIP remotely')


def _open_browser(url:str):
    try:webbrowser.open(url)
    except Exception:pass


def _lock_info(guard:ProcessGuard):
    try:return json.loads(guard.path.read_text(encoding='utf-8'))
    except Exception:return {}


def _set_lock_endpoint(guard:ProcessGuard,host:str,port:int):
    try:
        info=_lock_info(guard);info.update({'host':host,'port':port});guard.path.write_text(json.dumps(info),encoding='utf-8')
    except Exception:pass


def main()->None:
    guard=ProcessGuard(root=Path(settings.data_dir))
    if not guard.acquire():
        info=_lock_info(guard);host=str(info.get('host') or settings.host);port=int(info.get('port') or settings.port)
        url=f'http://{host}:{port}/'
        print(f'NOTSIP is already running; opening {url}')
        _open_browser(url)
        if getattr(sys,'frozen',False):os._exit(0)
        return
    try:
        if getattr(sys,'frozen',False):
            try:
                from notsip.update_recovery import reconcile_frozen_update
                recovery=reconcile_frozen_update(Path(settings.data_dir),Path(sys.executable),getattr(settings,'windows_publisher_thumbprint',''))
                if recovery.get('status')=='ROLLED_BACK':print(f"NOTSIP update recovery restored {recovery.get('backup')}")
                elif recovery.get('status')=='RECOVERY_UNAVAILABLE':raise RuntimeError('previous NOTSIP binary is invalid and no valid signed rollback binary is available')
            except RuntimeError:raise
            except Exception as exc:raise RuntimeError(f'NOTSIP update recovery failed: {exc}') from exc
        host=settings.host
        _validate_bind_security(host)
        port=_select_port(host,settings.port)
        if port==0:
            return
        settings.port=port
        os.environ['NOTSIP_EFFECTIVE_PORT']=str(port)
        _set_lock_endpoint(guard,host,port)
        from notsip.core_runtime import app
        if getattr(sys,'frozen',False):
            import notsip.runtime_prod as runtime_prod
            runtime_prod.ROOT=Path(getattr(sys,'_MEIPASS',Path.cwd()))
            if hasattr(runtime_prod,'maint'):
                runtime_prod.maint.root=Path(os.environ.get('NOTSIP_REPO_ROOT',Path.cwd())).resolve()
        url=f'http://{host}:{port}/'
        print(f'NOTSIP listening at {url}')
        if settings.open_browser:_open_browser(url)
        uvicorn.run(app,host=host,port=port,log_level=settings.log_level.lower())
    finally:
        guard.release()

if __name__=='__main__':main()
