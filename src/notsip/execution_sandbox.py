from __future__ import annotations
import os
import platform
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path


class ExecutionSandbox:
    """Run analysis code in a bounded disposable workspace without inherited secrets."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def run_python(self, code: str, timeout: int = 20, max_output: int = 50000) -> dict:
        code = str(code or "")
        if not code.strip():
            raise ValueError("code is required")
        if "\x00" in code:
            raise ValueError("NUL bytes are not allowed")
        timeout = max(1, min(int(timeout), 60))
        max_output = max(1000, min(int(max_output), 200000))
        run_dir = Path(tempfile.mkdtemp(prefix="notsip-code-", dir=self.root))
        script = run_dir / "main.py"
        script.write_text(textwrap.dedent(code), encoding="utf-8")
        env = {
            "PATH": os.getenv("PATH", ""),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUNBUFFERED": "1",
        }
        if platform.system() != "Windows":
            env["HOME"] = str(run_dir)
        started = time.time()
        try:
            p = subprocess.run(
                [sys.executable, "-I", "-S", str(script)],
                cwd=str(run_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            stdout = p.stdout[-max_output:]
            stderr = p.stderr[-max_output:]
            return {
                "status": "SUCCESS" if p.returncode == 0 else "FAILURE",
                "returncode": p.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "elapsed_sec": round(time.time() - started, 4),
                "workspace": str(run_dir.relative_to(self.root)),
                "verified": p.returncode == 0,
                "network_policy": "not provided by sandbox",
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "status": "FAILURE",
                "returncode": None,
                "stdout": (exc.stdout or "")[-max_output:] if isinstance(exc.stdout, str) else "",
                "stderr": (exc.stderr or "")[-max_output:] if isinstance(exc.stderr, str) else "",
                "elapsed_sec": round(time.time() - started, 4),
                "workspace": str(run_dir.relative_to(self.root)),
                "verified": False,
                "error": "execution timeout",
            }
