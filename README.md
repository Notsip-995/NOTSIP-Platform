# NOTSIP Platform

Standalone NOTSIP platform project. This repository is completely separate from `Notsip-995/NOTSIPAI`.

## Current track

`0.3.0-alpha` — installable integration platform. Adapters either call real configured services or return explicit availability/configuration errors. No fake telemetry or fabricated successful actions are intended.

## Structure

- `src/notsip/` — control plane, agent loop, persistent store, policy, tools, world model, events and jobs
- `android/` — Android companion / pairing / accessibility boundary
- `scripts/` — Windows installation and startup
- `docs/` — architecture
- `tests/` — smoke tests
- `releases/` — source release archive

## Windows setup

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install_windows.ps1
# Edit .env with real provider/service configuration
.\scripts\start_windows.ps1
```

Then open `http://127.0.0.1:8765`.

## Model

Set `NOTSIP_LLM_BASE_URL`, `NOTSIP_LLM_MODEL` and, when required, `NOTSIP_LLM_API_KEY`. The gateway uses the OpenAI-compatible chat-completions protocol and can point at a hosted or local inference endpoint.

## Security

Secrets are excluded from Git. Tool capabilities have risk classes and autonomy gates. Destructive/high-risk operations are blocked below the configured threshold. Android receives a device-scoped pairing token rather than provider API keys.

## Deferred

Robotics, satellite/remote-sensing, vehicle and building integrations remain disabled until real systems are available.

The `releases/NOTSIP-0.3.0-alpha.zip` archive is included as the original standalone package; the source tree in this repository is the authoritative clone target.
