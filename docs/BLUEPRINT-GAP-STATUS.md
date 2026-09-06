# NOTSIP blueprint gap status

## Built in 0.6.0-alpha

- Persistent identity and local state
- Conversational history
- Durable memory records with source/provenance fields
- World entities and relations
- Structured model tool calling over an OpenAI-compatible endpoint
- Local planning primitive
- Risk/autonomy policy and audit trail
- Isolated workspace file read/write
- Windows PowerShell execution boundary
- Windows desktop screenshot
- Playwright browser extraction boundary
- Live Brave web search
- Event bus and event ingress
- Device pairing, device-scoped tokens, heartbeat and command queue
- Android accessibility command boundary
- Windows 11 install/start scripts
- Android project skeleton
- Environment template with secrets excluded from Git
- Machine-specific deployment reconciliation

## Still dependency-gated

These are implemented as contracts/adapters but require the user's actual external account/device/service before they can operate: SMTP/IMAP mail, calendar provider OAuth, messaging providers, vision model endpoint, voice engine, speech-to-text, text-to-speech, phone UI automation permissions, remote node connections, smart-home controllers, MQTT brokers, databases and enterprise services.

## Deferred by hardware availability

Robotics, satellites/remote sensing, vehicles and building automation are intentionally not enabled because the reconnaissance reported no such target systems.

## Still engineering work

Production-grade secret vaulting, distributed node federation, durable queue/retry semantics, stronger authentication, full multimodal streaming voice/vision UX, richer source corroboration/fusion, model routing across multiple providers, broader application-specific Windows/Android automation, recovery/failover, and release-grade installers remain to be completed before calling the platform production-ready across the entire blueprint.
