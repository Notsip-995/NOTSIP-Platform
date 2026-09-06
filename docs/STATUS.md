# NOTSIP 0.8 status

The 0.8 runtime fixes the prior alpha release-blockers: the obsolete `server05.py` is removed, `server.py` is now only a compatibility alias to the authoritative runtime, the root route serves `ui.html`, advertised API routes are wired, scheduled tasks have registered handlers, and CI/Docker/regression tests are present.

Implemented and locally validated: persistent store/memory/world state, model tool loop with primary/fallback endpoints, autonomy policy, Windows node controls, browser extraction, web search, email/ICS/OAuth surfaces, background scheduled tasks, Android pairing and command/result transport, local UI, repository self-inspection, guarded self-maintenance with rollback, first-run configuration wizard, CI, and Docker runtime definition.

Runtime dependencies remain configuration-gated rather than simulated. Robotics, satellites/remote sensing, vehicles, building automation and other absent physical infrastructure remain deferred.
