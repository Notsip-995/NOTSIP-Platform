# NOTSIP blueprint gap status — 0.8

This document distinguishes actual implementation from external configuration and capabilities that cannot be validated until real hardware/services exist.

## Operational software in the repository

- authoritative `python -m notsip` runtime
- root web UI and FastAPI API documentation
- persistent identity, conversation history, SQL/FTS memory and provenance
- world entities and relations
- primary and fallback OpenAI-compatible model routing
- structured tool calling and risk/autonomy enforcement
- persistent scheduled tasks with registered agent/self-verification handlers
- signed event ingestion and live WebSocket event stream
- Windows workspace, PowerShell, screenshot and target-opening controls
- browser extraction through Playwright
- live web retrieval through Brave
- SMTP/IMAP and ICS calendar adapters
- OAuth status/authorize/callback surface
- Android pairing, heartbeat and command/result transport
- repository self-inspection, source reading, compile/test verification and guarded self-modification with temporary branch + rollback
- first-run Windows configuration wizard
- CI compile/test workflow
- Docker runtime definition
- regression test coverage for core, API, scheduler, pairing, workspace isolation and self-maintenance

## Requires real configuration / user action

- cloud or local LLM endpoint/model
- web search API credentials
- mail account and SMTP/IMAP settings
- OAuth application registration and consent for the chosen provider
- Android app installation and user-granted AccessibilityService permission
- any external smart-home/MQTT service

These capabilities intentionally report unavailable/degraded when not configured; they are not simulated.

## Physical/deployment-gated

- robotics and vehicle control
- satellites/remote sensing
- building automation
- Raspberry Pi/ESP32/sensor fleets
- distributed external clusters

These remain deferred until the corresponding real systems are available.

## Production-hardening still required before a universal 'fully complete' claim

- signed release binaries and auto-update channel
- production-grade OIDC/secret-vault deployment
- distributed node federation/recovery/failover
- high-fidelity application-specific desktop automation across arbitrary Windows apps
- full native streaming voice/wake-word/TTS and interruption handling
- multimodal camera ingestion and sustained perception
- deeper information corroboration/fusion and proactive trigger policy
