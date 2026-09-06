# NOTSIP implementation matrix

This matrix separates what the current platform implements from capabilities that require a real external service or physical system.

## Implemented in software

- natural-language API and web UI
- conversational history
- persistent SQL memory
- memory classes: short-term, episodic, semantic, preference, procedural, system
- world entities and relations
- model-provider abstraction using OpenAI-compatible chat completions
- structured tool calling
- capability/risk/autonomy policy
- explicit confirmation primitives
- audit trail
- evidence/provenance ledger
- task persistence and background worker foundation
- signed event ingestion and event streaming
- Windows node boundary with PowerShell execution in the authorized workspace
- Android device pairing token and heartbeat
- real public web search adapter
- degraded-service state tracking
- reproducible Windows setup scripts
- Docker deployment foundation

## Real adapters present but require configuration

- hosted/local LLM endpoint
- Brave Search
- Android companion
- SMTP/IMAP email
- Home Assistant/MQTT when those services are actually available

## Deferred until the real system exists

- robotics hardware control
- satellite/remote-sensing feeds
- vehicle/armor-like systems
- building automation hardware not present on the target machine
- specialized server clusters and external enterprise systems

## Still required for a production-complete NOTSIP

- hardened authentication/OIDC and a secrets manager
- production PostgreSQL/Redis deployment and worker queue
- full OAuth integrations for calendar/mail/messaging
- high-fidelity Windows GUI automation and screen perception
- Android command channel and user-approved accessibility actions beyond heartbeat/pairing
- streaming speech recognition, wake word, TTS and interruption handling
- camera/vision ingestion and multimodal perception
- richer source corroboration and information-fusion pipelines
- automatic proactive monitoring and policy-driven trigger evaluation
- distributed node synchronization, recovery and failover
- signed releases/installer distribution and update mechanism
