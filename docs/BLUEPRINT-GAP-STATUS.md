# NOTSIP blueprint gap status — 0.9

This document distinguishes implemented software from capabilities that require the user's real accounts, devices, permissions, signing material, or deferred physical hardware.

## Operational software implemented

- authoritative `python -m notsip` runtime and Windows EXE/installer path
- persistent identity, conversations, memory, provenance, world state and recovery checkpoints
- primary/fallback OpenAI-compatible provider routing
- risk/autonomy policy, persistent approvals and audited tool execution
- durable scheduler with registered handlers, retries, atomic claiming and worker recovery
- signed event ingress and authenticated WebSocket streams
- Windows PowerShell/UI Automation, screenshot, clipboard, mouse, target-opening and verification controls
- Playwright browsing with capability gating and private-address/SSRF protection
- Brave web retrieval and SMTP/IMAP/ICS adapters
- OIDC discovery, PKCE, encrypted pending state, durable browser sessions and account lifecycle
- Android pairing, foreground service, device authentication, atomic command delivery and device-bound results
- federation challenge/signature, token rotation, leases, revocation and reconciliation
- self-inspection, source reading, compile/test verification and guarded self-modification/update/rollback paths
- first-run configuration with persisted-state hydration and protected secret handling
- diagnostics, structured rotating logs, request IDs, audit records, backup/restore and configuration migration
- SQLite plus optional PostgreSQL storage interfaces
- actual Windows `NOTSIP.exe` and `NOTSIP-Setup.exe` lifecycle acceptance tests

## External configuration / environment gates

- selected LLM, STT and TTS provider accounts/endpoints
- web-search credentials
- SMTP/IMAP mail accounts
- OAuth application registrations/consent
- Android installation, pairing and OS Accessibility/background permissions
- real microphone/camera/audio hardware for native media behavior
- Windows code-signing certificate/private material for signed releases
- PostgreSQL server and credentials when that backend is selected

NOTSIP must report these as unavailable/degraded until the real resource is configured and tested; it must not fabricate success.

## Deferred physical systems

Robotics, vehicles, satellites/remote sensing, smart-building infrastructure, Raspberry Pi/ESP32 sensor fleets, and external physical clusters remain deferred because those systems are not present in the current environment.

## Validation rule

A release is not declared universally production-ready until the current `main` head passes the full automated release gate using the actual frozen Windows executable and installed Windows installer, and a fresh code audit finds no substantive repository defect. External account, OS permission, signing-material and physical-hardware checks remain real-environment gates.
