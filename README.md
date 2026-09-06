# NOTSIP Platform 0.8

Standalone NOTSIP platform for the Windows 11 laptop + Android phone target. This repository is completely separate from `Notsip-995/NOTSIPAI`.

## Install on Windows 11

```powershell
git clone https://github.com/Notsip-995/NOTSIP-Platform.git
cd NOTSIP-Platform
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install_windows.ps1
.\scripts\start_windows.ps1
```

The installer creates the Python environment, installs the development/runtime dependencies, installs Chromium for Playwright, and launches a guided first-run configuration wizard. The wizard writes `.env`, which is excluded from Git. It covers the model provider/fallback, web search, email, OAuth, Android pairing, API authentication, event signing, autonomy, and controlled self-maintenance settings.

After startup, open `http://127.0.0.1:8765` for the NOTSIP UI. API documentation is available from FastAPI at `/docs`.

## Runtime

The authoritative runtime is `python -m notsip`, which imports `src/notsip/core_runtime.py`. `src/notsip/server.py` is only a compatibility alias to that runtime; there is no second server implementation.

The platform provides persistent identity/context, SQL+FTS memory with provenance, world entities/relations, fact/evidence records, model tool calling with primary/fallback routing, risk/autonomy enforcement, confirmation gates, persistent scheduled jobs with registered handlers, signed event ingestion and WebSocket events, Windows execution/screenshot/open actions, Playwright browser extraction, live web retrieval, SMTP/IMAP email, ICS/OAuth scaffolding, Android pairing/device commands, a local web UI, self-inspection, verification, and controlled self-modification with a test-and-rollback workflow.

External capabilities are configuration-gated. NOTSIP does not fabricate success when an external dependency is unavailable.

## Self-awareness / self-maintenance

NOTSIP can inspect its repository, enumerate source files with SHA-256 hashes, read its own source, run compile/tests, and—only when explicitly enabled and approved—apply a supplied patch on a temporary Git branch. The patch is tested before commit; a failing change is rolled back. This is deliberate rather than unrestricted self-editing.

## Target hardware

Windows 11 Pro, Lenovo ThinkPad-class laptop, Intel Core i5-1335U, 16 GB RAM, Intel Iris Xe integrated graphics, microphone array, integrated cameras/IR camera, Wi-Fi 6E, Bluetooth, and Android phone companion. CUDA is not required.

## Deferred until real infrastructure exists

Robotics, satellites/remote sensing, vehicles, smart-building controllers, Raspberry Pi/ESP32 fleets, and specialized external clusters are not enabled until the corresponding real targets are connected.
