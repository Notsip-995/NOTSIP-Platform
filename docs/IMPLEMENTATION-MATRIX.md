# NOTSIP implementation matrix — current audit branch

This matrix is deliberately evidence-based. `Implemented` means the software exists and is integrated; `Tested` is reserved for automated validation that is actually executed. Real-device/provider/release validation remains separate.

| Capability | Implementation | Security/error handling | Automated test coverage | Real-world validation |
|---|---|---|---|---|
| Core runtime/API | Implemented | Authenticated protected routes, request IDs, structured errors | Existing core/API regression suite | Pending hosted runner execution |
| Configuration/Setup | Implemented | Fail-closed persistence, protected secrets, environment precedence, migration and masked UI | Config/migration/Setup regressions | Windows frozen/installed acceptance pending runner |
| Memory/conversations/profile | Implemented | Actor-scoped persistence; corruption fails closed | Scope/integrity regressions | Restart persistence pending executable run |
| World/perception state | Implemented | Actor-scoped relations/entities; explicit perception failures | World/perception regressions | Real screen/camera validation pending hardware |
| AI reasoning/tool execution | Implemented | Risk/autonomy policy, approval gate, durable workflows, verification semantics | Scheduler/workflow/security regressions | External model behavior pending configured provider |
| Windows automation | Implemented | Workspace/path controls and UIA partial-failure semantics | Windows API/verification regressions | Actual Windows EXE validation pending working runner |
| Linux integration | Implemented | Non-elevated workspace execution, sanitized environment | Linux/system-service regressions where available | Real Linux deployment not yet verified |
| Browser automation | Implemented | HTTPS/public-host checks, request interception, no credentials in URL | Browser security regressions | External web application validation pending |
| Voice/STT/TTS | Implemented | MIME validation, native WAV path, provider gating | Media-format/native-voice regressions | Real microphone/audio/provider validation pending |
| Speaker identity | Implemented | Verified speaker required for high-risk voice actions; evidence path confined | Voice-identity regressions | Real provider/model validation pending |
| Continuous perception | Implemented | Disabled by default unless explicitly enabled; change detection and interval control | Perception regressions | Real screen/camera validation pending |
| Android bridge | Implemented | Secure token storage, HTTPS remote transport, device ownership, durable result delivery | Android protocol/isolation regressions | Physical Android validation pending |
| OAuth/OIDC | Implemented | PKCE/state/nonce/CSRF, encrypted tokens, actor/account isolation, refresh merge | OAuth/OIDC/account tests | Real provider consent/revocation testing pending |
| Communications | Implemented | Actor/device ownership, high-risk approval | Communication regressions | Real mail/SMS provider validation pending |
| Federation/distributed nodes | Implemented | HMAC challenge, replay protection, leases, ownership, revoke/rotate, failover | Federation/concurrency regressions | Multi-node real deployment pending |
| Robotics/external physical systems | Partially implemented | Authenticated adapters + safety/verification boundaries | Adapter/unit coverage | Physical hardware pending |
| Business administration | Implemented | Endpoint/token validation; mutation success must be explicit | Business-admin regressions | Real enterprise system pending |
| Recovery/backup | Implemented | Integrity manifests, staged restore, rollback, device-token preservation, redacted restore routes | Recovery/backup regressions | Full failure/restart drill pending executable environment |
| Updates/self-maintenance | Implemented | Trusted GitHub source, SHA-256, Authenticode publisher check, signed rollback recovery | Updater/recovery regressions | Signed release artifact validation pending credentials/runner |
| Packaging/installer | Implemented | Per-user least privilege; signed release gate | Release/launcher regressions | Actual EXE/installer execution pending working runner |
| PostgreSQL | Implemented interface | Transactional task/command claiming and concurrency hardening | PostgreSQL concurrency contract tests | Real PostgreSQL integration pending |
| Docker | Implemented | Non-loopback bind requires auth; runtime smoke configured with disposable CI key | Docker smoke in CI workflow | Hosted runner currently unavailable |

## Current validation blockers

- GitHub Actions jobs on the audit branch are currently terminating before runner execution (`runner_id: 0`, no steps/logs exposed by the connected GitHub API). This prevents honest claims of a passing automated/release test suite.
- Windows release artifact execution, Android device behavior, external OAuth/provider behavior, PostgreSQL integration, signing, microphone/camera and physical robotics/sensor validation require their respective real environments.

## Release rule

Do not treat implementation or code review as equivalent to release validation. The blueprint release gate requires successful relevant automated tests, actual frozen Windows/installer acceptance, persistence/restart verification, recovery verification, and explicit separation of real external/hardware validation.
