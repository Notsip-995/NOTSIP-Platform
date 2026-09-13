#!/usr/bin/env python3
"""NOTSIP one-shot installer (cross-platform).

Run from the repository root after unpacking the zip:

    python scripts/install.py          # or: python3 scripts/install.py

What it does:
  1. Verifies Python >= 3.12 is available.
  2. Creates a virtual environment (.venv).
  3. Installs NOTSIP + runtime/windows/dev dependencies.
  4. Installs Chromium for Playwright (Windows).
  5. Ensures the data directories exist.
  6. Launches NOTSIP for the first-run setup wizard and opens the dashboard.

Nothing here fakes a result: every step must succeed before the wizard opens.
Secrets are configured in the in-app Setup wizard (source of truth), never by
this script into a plaintext .env.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
REQUIRED_PY = (3, 12)


def _err(msg: str) -> None:
    print(f'\n[NOTSIP installer] ERROR: {msg}', file=sys.stderr)


def _warn(msg: str) -> None:
    print(f'\n[NOTSIP installer] WARNING: {msg}', file=sys.stderr)


def _info(msg: str) -> None:
    print(f'[NOTSIP installer] {msg}')


def _venv_bin() -> Path:
    if sys.platform == 'win32':
        return ROOT / '.venv' / 'Scripts'
    return ROOT / '.venv' / 'bin'


def _python() -> Path:
    exe = 'python.exe' if sys.platform == 'win32' else 'python'
    return _venv_bin() / exe


def _venv_exists() -> bool:
    return _python().exists()


def _check_system_python() -> None:
    if sys.prefix == sys.base_prefix:
        # The script is running outside a venv; that's fine. Verify version and
        # the ability to create a venv.
        if sys.version_info[:2] < REQUIRED_PY:
            msg = (f'Python {REQUIRED_PY[0]}.{REQUIRED_PY[1]}+ is required; '
                   f'found {sys.version_info.major}.{sys.version_info.minor}.')
            if sys.platform == 'win32':
                msg += ' Install Python 3.12+ from https://www.python.org/downloads/ and re-run.'
            _err(msg)
            sys.exit(1)
    else:
        _warn('install.py is already running inside a virtual environment; '
              'NOTSIP will reuse it instead of creating .venv')


def _create_venv() -> None:
    if _venv_exists():
        _info('virtual environment already present; reusing .venv')
        return
    _info('creating virtual environment .venv ...')
    try:
        subprocess.run([sys.executable, '-m', 'venv', str(ROOT / '.venv')],
                       check=True, cwd=ROOT)
    except subprocess.CalledProcessError as exc:
        _err(f'could not create virtual environment: {exc}')
        sys.exit(1)


def _run(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    _info('> ' + cmd)
    return subprocess.run(cmd, shell=True, cwd=ROOT, check=check)


def _pip_install(extra: str) -> None:
    py = _python()
    _run(f'"{py}" -m pip install --disable-pip-version-check --upgrade pip')
    _run(f'"{py}" -m pip install --disable-pip-version-check -e ".[{extra}]"')


def _playwright_install() -> None:
    py = _python()
    try:
        _run(f'"{py}" -m playwright install chromium')
    except subprocess.CalledProcessError as exc:
        _warn(f'Playwright Chromium install failed ({exc}). NOTSIP can still run; '
              'browser automation will be unavailable until you run '
              '".venv\\Scripts\\python -m playwright install chromium".')


def _ensure_dirs() -> None:
    for name in ('workspace', 'screenshots', 'audio', 'perception', 'recovery',
                 'runtime', 'backups', 'updates'):
        (DATA / name).mkdir(parents=True, exist_ok=True)
    _info(f'data directory ready: {DATA}')


def _wait_for_setup(timeout: int = 60) -> str:
    """Wait for NOTSIP to serve /setup; return the effective URL."""
    base = 'http://127.0.0.1:8765'
    lock = DATA / 'runtime' / 'instance.lock'
    deadline = time.time() + timeout
    while time.time() < deadline:
        if lock.exists():
            try:
                import json
                info = json.loads(lock.read_text(encoding='utf-8'))
                if info.get('host') and info.get('port'):
                    base = f"http://{info['host']}:{info['port']}"
            except Exception:
                pass
        try:
            with urllib.request.urlopen(f'{base}/setup', timeout=1) as r:
                if r.status == 200:
                    return f'{base}/setup'
        except Exception:
            pass
        time.sleep(0.5)
    return f'{base}/setup'


def _launch() -> None:
    py = _python()
    kwargs = {}
    if os.name == 'nt':
        kwargs['creationflags'] = 0x00000008  # DETACHED_PROCESS
    proc = subprocess.Popen(
        [str(py), '-m', 'notsip'],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = _wait_for_setup()
    _info(f'NOTSIP is starting. Complete setup at {url}')
    try:
        webbrowser.open(url)
    except Exception:
        pass
    _info(f'If the browser did not open, visit {url}')
    _info(f'NOTSIP process id: {proc.pid}. The terminal that runs it is detached; '
          'use scripts/start_windows.ps1 / scripts/start.sh to manage it.')


def main() -> None:
    _check_system_python()
    _create_venv()
    _ensure_dirs()
    _pip_install('dev,windows' if os.name == 'nt' else 'dev')
    if os.name == 'nt':
        _playwright_install()
    _launch()
    _info('Install complete. If you have any issues, run with the latest output to '
          'troubleshoot: python -m notsip at the repository root.')


if __name__ == '__main__':
    main()