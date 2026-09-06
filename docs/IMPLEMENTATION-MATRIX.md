# NOTSIP implementation matrix — 0.8

## Implemented and wired

- single authoritative `python -m notsip` runtime
- functional root web UI plus FastAPI API docs
- persistent identity, conversation history and SQL/FTS memory
- memory provenance/source fields
- world entities and relations
- primary OpenAI-compatible model with fallback model support
- structured tool calling
- capability/risk/autonomy policy and confirmation boundaries
- persistent audit trail and evidence/fact ledger
- persistent scheduled tasks
- registered `agent` and `self_verify` scheduler handlers
- explicit task run endpoint
- signed external event ingestion and WebSocket event stream
- Windows PowerShell, desktop screenshot and open-target controls
- isolated NOTSIP workspace
- Playwright page extraction
- live Brave web search adapter
- SMTP/IMAP mail adapters and status/search/send routes
- ICS calendar parser and OAuth status/authorize/callback routes
- Android pairing, heartbeat, command queue, result reporting and command executor
- repository self-inspection, source reading, compile/test verification and guarded self-modification with branch + rollback
- interactive Windows first-run configuration wizard
- CI compile/test workflow
- Docker runtime definition
- regression tests for API, pairing, workspace isolation, scheduler and self-maintenance

## Configuration-gated capabilities

These become operational when their real endpoint/account/permission is supplied during first-run configuration: model providers, web search, SMTP/IMAP, OAuth providers, Android AccessibilityService, and other external services.

## Deferred by hardware availability

Robotics, satellite/remote-sensing feeds, vehicles, smart-building controllers, Raspberry Pi/ESP32 fleets, and specialized external infrastructure remain disabled until the corresponding real systems exist.

## Not claimed as complete merely by having an adapter

High-fidelity multimodal voice/wake-word processing, deep application-specific GUI automation, full production OIDC/secrets-vault deployment, distributed-node consensus/failover, advanced information-fusion/corroboration, and production-grade release signing/update infrastructure still require additional engineering and real deployment validation.
