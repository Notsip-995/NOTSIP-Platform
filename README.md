# NOTSIP Platform

Standalone NOTSIP project. This repository is completely independent from `Notsip-995/NOTSIPAI`.

## 0.5.0 operational baseline

The executable entrypoint is `python -m notsip`, backed by `src/notsip/runtime05.py`. It provides a persistent local control plane with memory, model tool-calling, autonomy gates, Windows execution boundaries, desktop screenshot/open actions, web search, persistent tasks, signed events, Android pairing, device command polling, email/ICS/OAuth/vision configuration surfaces, and an explicit degraded mode when a real dependency is unavailable.

Nothing in this repository fabricates device telemetry or claims an external action succeeded without a real adapter result.

## Windows 11 setup

```powershell
git clone https://github.com/Notsip-995/NOTSIP-Platform.git
cd NOTSIP-Platform
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install_windows.ps1
notepad .env
.\scripts\start_windows.ps1
```

Open `http://127.0.0.1:8765`.

## Real provider

Set `NOTSIP_LLM_BASE_URL`, `NOTSIP_LLM_MODEL`, and `NOTSIP_LLM_API_KEY` when required. The provider uses the OpenAI-compatible `/chat/completions` contract, so it can point to a hosted or local inference server.

## Android

The companion uses a short-lived pairing code and a device-scoped token. Provider secrets stay on the NOTSIP node. Android UI automation is bounded by the user-enabled AccessibilityService permission. Google Play requires new apps/updates to target Android 16 (API 36) from August 31, 2026. citeturn987980search0 Android also requires AccessibilityService to be explicitly enabled by the user. citeturn987980search1

## Security

Secrets are excluded from Git. High-risk tools are autonomy-gated. Workspace file operations are sandboxed. Pairing tokens are hashed at rest. Use a dedicated secret manager for production deployment.

## Current hardware target

The design is tuned for the supplied Lenovo Windows 11 Pro laptop (Intel i5-1335U, 16 GB RAM, Intel Iris Xe) plus an Android phone. CUDA is not required. Docker, local PostgreSQL/Redis, robotics, satellites, vehicles, Raspberry Pi, ESP32 and smart-home hardware are optional rather than prerequisites.

## Deferred by design

Robotics, satellite/remote sensing, vehicle systems and building automation are disabled until real target infrastructure exists. Google/Microsoft/messaging OAuth requires actual developer registrations and user authorization; those interfaces are present, but the platform will not invent access.
