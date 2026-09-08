# NOTSIP 45-item production acceptance matrix

This document is the implementation contract derived from the project defect audit. “Implemented” means the repository contains the runtime path and regression coverage; “Environment-gated” means the code is complete but the user's account/device/permission is inherently required; “Deferred” means the target hardware/service does not exist in the current environment.

| # | Acceptance item | Status | Validation / implementation |
|---|---|---|---|
|1|Frozen EXE resource resolution|Implemented|PyInstaller resource_root + EXE smoke loads UI|
|2|Complete installer|Implemented|Inno Setup `NOTSIP-Setup.exe` definition + CI build|
|3|Frozen self-maintenance/update|Environment-gated|Frozen runtime can inspect/verify durable source; binary replacement uses guarded updater; Git patching requires a durable Git checkout|
|4|Port collision|Implemented|Launcher detects occupied port and selects free port / reuses running NOTSIP|
|5|Single instance|Implemented|ProcessGuard + duplicate-launch service/listener validation|
|6|Lifecycle management|Implemented|start/stop/restart/status/setup PowerShell launcher + startup shortcut|
|7|Graphical first-run wizard|Implemented|setup.html covers runtime, providers, media, security, DB, intervals and updates|
|8|Capability validation|Implemented|diagnostics/capability probe shown during setup and in console|
|9|Secret separation|Implemented|DPAPI/AES-GCM secret store; config excludes secret values|
|10|Config migration|Implemented|versioned ConfigStore schema and migration hook|
|11|Operating console|Implemented|dashboard, memory, tasks, devices, security, integrations, diagnostics, backup|
|12|Browser auth|Implemented|HttpOnly server-side session; no localStorage bearer API key|
|13|Missing capability guidance|Implemented|capability/diagnostic views plus setup navigation|
|14|Durable OIDC sessions|Implemented|encrypted durable OIDC pending/session state plus browser session persistence|
|15|Android command-result auth|Implemented|device ID + device token required; command result is bound to authenticated device|
|16|Pairing protections|Implemented|short-lived one-use pairing codes, rate limiting, device token/revocation/audit|
|17|Federation auth lifecycle|Implemented|HMAC challenge/sign/verify, token rotation, lease, revoke, reconciliation|
|18|Android polished companion|Environment-gated|APK builds; runtime/device smoke script; permissions are device-side|
|19|Android release APK/AAB|Environment-gated|signed release configuration + CI artifact path; user keystore is required|
|20|Android lifecycle hardening|Implemented|foreground service + boot/package-replaced receiver + reconnect backoff|
|21|Streaming voice|Implemented|WebSocket STT relay when `stt_stream_url` is configured; buffered fallback retained|
|22|VAD/wake phrase|Implemented|native worker VAD + configurable wake phrase|
|23|Native Windows voice|Environment-gated|native worker implemented; microphone/provider must be configured on host|
|24|Continuous perception|Implemented|desktop frame sampling, change detection, vision observation and events|
|25|Screen perception|Environment-gated|Windows screenshot/vision loop; requires Windows + vision provider|
|26|Broad Windows automation|Implemented|UIA tree, discovery, focus, click, type, hotkeys, clipboard, mouse, waits|
|27|Action verification|Implemented|UIA click/type verification and agent audit results|
|28|Degraded fallback|Implemented|safe deterministic fallback + primary/fallback provider routing|
|29|Persistent approval workflow|Implemented|approval records, explicit decision, execution and audit|
|30|Durable conversation model|Implemented|persistent sessions/messages/summaries + APIs|
|31|Long-term memory lifecycle|Implemented|episodic/semantic/procedural/working/preference/relationship/system/perception kinds, decay and consolidation|
|32|World model|Implemented|persistent entities/relations/facts and perception-fed world architecture|
|33|Event-driven reasoning loop|Implemented|perception events can trigger agent review at higher autonomy levels|
|34|Durable scheduler|Implemented|worker ownership, atomic claim/reclaim, retries, idempotency keys and persistent execution metadata|
|35|Separate supervisor intervals|Implemented|health/checkpoint/proactive/memory intervals are distinct settings|
|36|Recovery|Implemented|checkpoints, verification, recoverable-state restore into runtime state, redispatch plans|
|37|OAuth account lifecycle|Implemented|Google/Microsoft OIDC + encrypted per-account token storage + account records + disconnect/revoke|
|38|Web provenance|Implemented|retrieval source, URL, timestamp, confidence, metadata and corroboration hooks|
|39|PostgreSQL|Environment-gated|optional psycopg backend behind existing Store interface; real server/credential is environment-dependent|
|40|Backup/restore UI|Implemented|create/list/verify/restore with explicit confirmation, staging and path-safety checks|
|41|Structured logging|Implemented|JSON logs, rotation, request IDs, audit records|
|42|Diagnostics center|Implemented|runtime/storage/db/LLM/STT/TTS/vision/web/email/OAuth/UIA/Android/scheduler/federation/recovery/security checks|
|43|Deep CI|Implemented|compile, tests, Docker, actual EXE lifecycle, installer build, Android build|
|44|Windows installer|Implemented|Inno Setup source and CI artifact build + installed-copy smoke|
|45|Automatic update/recovery|Implemented|trusted GitHub release check, artifact verification, backup + health verification + rollback path|

## Final product gate

A release is not considered production-ready until the latest CI Windows job passes the actual frozen `NOTSIP.exe` lifecycle: clean start, setup page, real configuration POST, operational console, health, status, diagnostics, persistence across restart, duplicate-launch behavior, installer creation, and installed-copy smoke.

External account authorization, OS permissions, signing material and absent physical hardware remain user/environment gates rather than simulated “success.”

Audit refresh: 2026-09-08 — current `main` was re-audited after the live-configuration fixes; no placeholder/simulator markers or legacy `server05.py`/`OpenAICompatible` path remain in the current source tree.
