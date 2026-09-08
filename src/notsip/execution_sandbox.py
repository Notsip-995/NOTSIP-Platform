from __future__ import annotations
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


class ExecutionSandbox:
    """Execute analysis code in a disposable container with no network access."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.image = os.getenv("NOTSIP_SANDBOX_IMAGE", "python:3.12-alpine")

    def run_python(self, code: str, timeout: int = 20, max_output: int = 50000) -> dict:
        code = str(code or "")
        if not code.strip():
            raise ValueError("code is required")
        if "\x00" in code:
            raise ValueError("NUL bytes are not allowed")
        timeout = max(1, min(int(timeout), 60))
        max_output = max(1000, min(int(max_output), 200000))
        docker = shutil.which("docker")
        if not docker:
            return {"status": "BLOCKED", "verified": False, "error": "container sandbox runtime is unavailable"}
        run_dir = Path(tempfile.mkdtemp(prefix="notsip-code-", dir=self.root))
        script = run_dir / "main.py"
        script.write_text(code, encoding="utf-8")
        started = time.time()
        try:
            cmd = [
                docker, "run", "--rm", "--network=none",
                "--cpus=1", "--memory=256m", "--pids-limit=64",
                "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                "-v", f"{run_dir}:/work:rw", "-w", "/work",
                self.image, "python", "/work/main.py",
            ]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return {
                "status": "SUCCESS" if p.returncode == 0 else "FAILURE",
                "returncode": p.returncode,
                "stdout": p.stdout[-max_output:],
                "stderr": p.stderr[-max_output:],
                "elapsed_sec": round(time.time() - started, 4),
                "workspace": str(run_dir.relative_to(self.root)),
                "verified": p.returncode == 0,
                "network_policy": "container network disabled",
                "resource_policy": "1 CPU, 256 MiB, 64 processes",
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
        finally:
            try:
                shutil.rmtree(run_dir)
            except OSError:
                pass
