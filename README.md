# NOTSIP Platform 0.9

NOTSIP is a persistent local AI operating layer for the Windows 11 laptop + Android companion target. This repository is deliberately separate from `Notsip-995/NOTSIPAI`.

## First install

```powershell
git clone https://github.com/Notsip-995/NOTSIP-Platform.git
cd NOTSIP-Platform
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install_windows.ps1
.\scripts\start_windows.ps1
```

The installer creates the Python environment, installs runtime and Windows UI Automation dependencies, installs Chromium for Playwright, creates the data directories, and runs the first-run configuration wizard. The wizard covers model/fallback routing, STT/TTS, visual perception, browser/web access, email, Google/Microsoft/generic OIDC, OAuth integration, API authentication, Android pairing, autonomy, event signing, federation, and controlled self-maintenance.

After startup, open `http://127.0.0.1:8765`; FastAPI documentation is at `/docs`.

## Production runtime

`python -m notsip` loads one canonical application assembly. `src/notsip/runtime.py`, `src/notsip/core_runtime.py`, and `src/notsip/server.py` are compatibility aliases only; they do not contain alternate server implementations.

The platform provides persistent identity/context, SQL+FTS memory with provenance, world entities/relations and evidence records, primary/fallback model routing, risk/autonomy enforcement, durable scheduled jobs with retry/backoff, signed events, Windows PowerShell + screenshot + UI Automation, Playwright browsing, web search, SMTP/IMAP and ICS support, Google/Microsoft OIDC/OAuth integrations, Android pairing/device transport, browser microphone/camera controls, streaming voice/perception sockets, self-inspection/self-verification/guarded self-maintenance, node leases and recovery checkpoints, and model-independent planning/evidence/contradiction/proactive-intelligence services.

External capabilities remain configuration-gated. NOTSIP never fabricates external success.

## Security

On Windows, secrets are protected with DPAPI-backed key material and AES-GCM encrypted local storage. OIDC uses discovery, authorization-code PKCE, state/nonce protection, JWKS-backed ID-token verification, issuer/audience/time validation, and HttpOnly sessions. Event ingress supports HMAC signatures. High-risk computer actions, outbound mail, and self-modification remain policy-gated.

## Self-awareness

NOTSIP can inventory and hash its source workspace, read its own source/configuration, compile and test itself, and—only when explicitly enabled and approved—apply a Git patch on a durable Git checkout. Changes are tested before commit and failed changes are rolled back. A frozen installed build can inspect and verify its durable source workspace; replacement of the running binary is handled through the guarded update/rollback path rather than by rewriting the running PyInstaller bundle in place.

## Windows automation

The Windows layer combines PowerShell for system-level actions with UI Automation through `pywinauto` for window enumeration/focus, control clicks, text entry, hotkeys, and additional application-specific interactions.

## Voice and perception

The web UI records microphone input for STT, plays returned TTS audio, and captures camera frames for vision. `/ws/voice` and `/ws/perception` are available for richer clients.

## Distributed nodes and recovery

Nodes use device-scoped tokens and renewable leases. NOTSIP reconciles stale nodes, produces recovery plans, persists state checkpoints, restores checkpoint state into runtime storage, and retries failed scheduled work with exponential backoff. Hardware-specific actions remain capability-gated.

## Windows executable

Build locally with `.\scripts\build_exe.ps1`. The Windows release workflow builds `dist\NOTSIP.exe` directly on a Windows runner and publishes the executable for tagged releases; repository development does not depend on ZIP archives.

## Target

Windows 11 Pro laptop with Intel Core i5-1335U, 16 GB RAM, Intel Iris Xe, integrated microphone/cameras, Wi-Fi/Bluetooth, plus Android companion. CUDA is not required.

## Physical systems

Robotics, vehicles, satellites/remote sensing, smart-building controllers, Raspberry Pi/ESP32 fleets, and other physical infrastructure are not simulated. Their adapters activate only when real systems are connected and authorized.
