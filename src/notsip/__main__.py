from __future__ import annotations

import os
import socket
import sys
import time
from pathlib import Path

import uvicorn

from notsip.config import settings
from notsip.core_runtime import app


def _is_notsip_listener(host: str, port: int) -> bool:
    """Return True when an existing listener answers as NOTSIP."""
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://{host}:{port}/api/health", timeout=0.8) as response:
            return response.status == 200 and "NOTSIP" in response.read().decode("utf-8", "replace")
    except Exception:
        return False


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def _select_port(host: str, configured: int) -> int:
    if not _port_in_use(host, configured):
        return configured
    if _is_notsip_listener(host, configured):
        print(f"NOTSIP is already running at http://{host}:{configured}/")
        return 0
    # Avoid a hard crash when another application owns the configured port.
    for candidate in range(configured + 1, configured + 21):
        if not _port_in_use(host, candidate):
            print(f"Port {configured} is busy; NOTSIP will use port {candidate}.")
            return candidate
    raise RuntimeError(f"No free port found in {configured}-{configured + 20}")


def _frozen_resource_root() -> Path | None:
    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass) if meipass else None


def main() -> None:
    # PyInstaller extracts bundled resources into _MEIPASS. The source-tree
    # repository-root calculation used by the runtime is intentionally not
    # valid there, so point the UI resource lookup at the frozen bundle.
    frozen_root = _frozen_resource_root()
    if frozen_root is not None:
        import notsip.runtime_prod as runtime_prod
        runtime_prod.ROOT = frozen_root
        # Self-maintenance must never treat the temporary PyInstaller bundle
        # as a writable source repository.
        if hasattr(runtime_prod, "maint"):
            runtime_prod.maint.root = Path(os.environ.get("NOTSIP_REPO_ROOT", Path.cwd())).resolve()

    host = settings.host
    port = _select_port(host, settings.port)
    if port == 0:
        return

    # Keep the effective port visible to the rest of the process and to status
    # consumers. Do not mutate the persisted configuration file.
    os.environ["NOTSIP_EFFECTIVE_PORT"] = str(port)
    settings.port = port
    print(f"NOTSIP listening at http://{host}:{port}/")
    uvicorn.run(app, host=host, port=port, log_level=os.getenv("NOTSIP_LOG_LEVEL", "info"))


if __name__ == "__main__":
    main()
