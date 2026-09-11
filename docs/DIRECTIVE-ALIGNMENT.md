# NOTSIP construction directive — alignment record

Spec authority: local `C:\me\readme.md` (Dan Piston NOTSIP blueprint: persistent AI operating layer — user -> NOTSIP core -> memory/information/execution -> external world, with honesty/uncertainty/permission/autonomy gates).

Repo source of truth: `Notsip-995/NOTSIP-Platform` on GitHub. This file tracks the ONE-coherent-runtime work. It is not a second implementation.

## Finding (2026-09-11, via GitHub API, no local checkout)

- Canonical boot is `python -m notsip` (`src/notsip/__main__.py`) -> `from notsip.core_runtime import app`.
- `core_runtime.py` (172 lines) assembles `app.py` + `runtime_prod.py` instances plus ~50 hardening/route attaches, then `normalize_routes(app)`.
- `runtime.py` / `server.py` are 1-line aliases (`from .app import app`). Good: no parallel server there.
- BUT `src/notsip/runtime_enterprise.py` (~23k chars) is a second full runtime graph (own FastAPI app, Store/Policy/Provider/Registry/Agent/World/Jobs/Media/Nodes/Auth instances) sitting beside `runtime_prod.py` (~15k chars). `runtime_enterprise.py` is NOT imported by `__main__`/`core_runtime`/`app`; nothing in the canonical boot uses it. That is the parallel-implementation smell the directive forbids.
- `core.py` (~10k chars) is a legacy EventBus/DB core, also outside the canonical boot.
- Tests (`test_production_layers.py`, `test_runtime.py`) assert against `notsip.core_runtime.app` only — they do not cover `runtime_enterprise`.

## Directive decision

- ONE coherent runtime = `__main__` -> `core_runtime.app` (authoritative instances live in `runtime_prod` + `app`, extended only by `*_hardening`/`*_routes` attaches).
- Do NOT expand `runtime_enterprise.py`. Treat it as legacy implementation material: retain for one release while wrapping/deprecating, then delete — never a second production graph.
- Do NOT rewrite working hardening attaches for style; only rewire what the blueprint requires (perception -> context -> memory -> reasoning -> planning -> authorization -> action -> observation -> memory loop, honest failure semantics).
- Validation is GitHub Actions on pushed branches (billing-blocked at last check 2026-09-11: `account payments failed / spending limit`). Code changes still land as branch commits + PR; CI concludes there, never locally.

## Next steps

1. Deprecation shim on `runtime_enterprise.py` pointing at `core_runtime.app` (no behavior change, kills the dual-graph trap).
2. Blueprint gap pass: wire any missing perception/context/authorization honest-failure paths through attaches, not a new app.
3. Push each step to `fix/notsip-directive-alignment`, open PR to `main`, let Actions validate.