# NOTSIP blueprint gap status — current hardening branch

This document is a truth-tracking aid for the chat-provided NOTSIP engineering blueprint. It does not override the blueprint itself and must not be read as release approval.

## Implemented in the current source tree

- authoritative `python -m notsip` runtime and Windows EXE/installer build paths
- persistent actor identity, conversations, memory, profiles, facts, world state and recovery state
- capability/risk/autonomy policy, durable approvals and central tool execution gate
- actor-scoped workspace, devices, tasks, approvals, OAuth accounts, notifications, audit/facts/world evidence
- durable scheduler with atomic task claiming, idempotency, deadlines, retries, continuation and workflow resume
- event journal, evidence/fusion, event reconstruction, predictive-maintenance analysis and proactive notification paths
- Windows PowerShell/UI Automation/screenshot/clipboard/mouse/target-opening controls with explicit verification semantics
- Linux command surface with workspace confinement and non-elevating execution
- Playwright browser interaction with public-endpoint/redirect/SSRF controls and bounded actions
- web/news/weather/navigation/flight-planning provider adapters with fail-closed external configuration
- SMTP/IMAP/calendar/OAuth account integration with scope/account isolation and truthful delivery semantics
- OIDC discovery, PKCE, state/nonce/CSRF/session protection and durable session revocation
- Android pairing, foreground service, secure token storage, device ownership, command claiming, durable result delivery and replay protection
- federation challenge/signature, one-use nonces, leases, revocation, ownership checks, reconciliation and stale-node handling
- home/building, biometric telemetry, business administration and remote compute/sensing adapters with high-risk policy boundaries
- read-only database routing with write/multi-statement rejection
- threat assessment, forensics, audit verification, backup integrity and rollback-safe recovery
- self-inspection, guarded self-modification, signed update provenance, SHA-256 verification, publisher verification and interrupted-update recovery
- first-run Setup UI, configuration migration, protected secret handling and readiness reporting

## Not yet validated as a release artifact

The source tree has not been locally executed in the current engineering environment, and GitHub Actions jobs for recent commits have repeatedly failed before exposing executable runner steps. Therefore the following are **not** marked as tested merely because code exists:

- full unit/integration/regression/concurrency/security/E2E suite
- frozen Windows executable startup and installed-copy acceptance
- Windows installer install/upgrade/uninstall acceptance
- Android release build plus real-device behavior
- PostgreSQL real-environment behavior
- signed production release artifacts

## User/environment configuration gates

These are intended to become operational when the user supplies the corresponding real resource:

- primary/fallback LLM provider credentials/endpoints
- STT/TTS providers and native audio hardware
- web-search credentials
- SMTP/IMAP mail accounts
- OAuth/OIDC application registration and provider consent
- Android installation, pairing and required OS permissions
- Windows signing certificate/private signing material
- PostgreSQL service/credentials when that backend is selected
- real remote sensing, business, building-control, biometric, compute or aviation providers

The application should report missing configuration as unavailable/degraded and never fabricate successful access.

## Physical/environment-gated capabilities

Robotics, vehicles, physical sensor fleets, smart-building hardware, satellite feeds, microphones/cameras, Android hardware behavior, and other specialized external systems require their real environments for final validation. Software-side interfaces and safety/error semantics are implemented where possible, but physical execution is not claimed here.

## Release rule

The authoritative blueprint requires: implementation → integration → security → failure handling → tests → fresh audit → packaging → release validation. This branch is therefore an engineering/hardening branch until the current source passes the applicable automated and packaged-product gates in a real execution environment.
