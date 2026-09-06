# NOTSIP 0.5 status

## Operational baseline

- Persistent local memory and conversation context
- World/device state storage
- Model tool-calling through OpenAI-compatible endpoints
- Primary/fallback model configuration
- Autonomy/risk gates
- Windows PowerShell execution boundary
- Workspace file sandbox
- Desktop screenshot/open actions
- Live Brave search
- Persistent tasks and signed event ingestion
- Android device pairing, heartbeat and command queue
- Email, ICS-calendar and generic OAuth configuration surfaces
- Provider-ready image/vision endpoint

## Requires configuration or user permission

- Cloud/local model endpoint
- Brave Search API key
- SMTP/IMAP account
- Google/Microsoft or other OAuth application registration
- Vision model endpoint
- Android AccessibilityService enablement

## Hardware deferred by design

Robotics, satellite/remote sensing, vehicles, smart-home/building automation and external sensor networks are disabled until real target systems exist.

## Production hardening still recommended

Use PostgreSQL/Redis for multi-node deployment, OIDC/passkeys and a secrets manager, signed device command envelopes/rotation, TLS at the edge, service monitoring, backups and release signing.
