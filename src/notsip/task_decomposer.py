from __future__ import annotations
from dataclasses import dataclass, asdict
import re

@dataclass(frozen=True)
class Subtask:
    id: int
    objective: str
    category: str
    dependencies: tuple[int, ...] = ()
    completion_condition: str = "verified result"

class TaskDecomposer:
    """Deterministic decomposition scaffold used before LLM execution planning."""
    def decompose(self, objective: str) -> dict:
        text = " ".join(str(objective or "").split())
        if not text:
            return {"status":"FAILURE","error":"objective is required","subtasks":[]}
        low = text.lower()
        steps: list[Subtask] = []
        def add(obj, cat, deps=()): steps.append(Subtask(len(steps)+1, obj, cat, tuple(deps)))
        if any(k in low for k in ("meeting", "schedule", "tomorrow", "calendar")):
            add("Resolve the relevant date and schedule context", "calendar")
            add("Identify matching event, participants and conflicts", "calendar", (1,))
        if any(k in low for k in ("report", "document", "file", "briefing")):
            deps=(steps[-1].id,) if steps else ()
            add("Retrieve relevant authorized documents and prior correspondence", "retrieval", deps)
            add("Extract facts, decisions and unresolved items", "analysis", (steps[-1].id,))
        if any(k in low for k in ("server", "slow", "performance", "diagnostic")):
            deps=(steps[-1].id,) if steps else ()
            add("Collect current system telemetry and recent errors", "diagnostics", deps)
            add("Compare current measurements with historical baseline", "analysis", (steps[-1].id,))
        if any(k in low for k in ("investigate", "behind", "why", "incident", "forensic")):
            deps=(steps[-1].id,) if steps else ()
            add("Collect independent authorized sources and timestamp evidence", "investigation", deps)
            add("Correlate evidence and state competing hypotheses", "analysis", (steps[-1].id,))
            add("Verify the strongest hypothesis where safe", "verification", (steps[-1].id,))
        if not steps:
            add("Understand objective, constraints and success criteria", "understanding")
            add("Execute the minimum-risk authorized action", "execution", (1,))
            add("Verify the resulting external state", "verification", (2,))
        return {"status":"SUCCESS","objective":text,"subtasks":[asdict(x) for x in steps],"completion_condition":"all required subtasks have verified outcomes"}

    def critical_path(self, plan: dict) -> list[int]:
        result=[]
        for item in plan.get("subtasks",[]):
            if not item.get("dependencies"): result.append(item["id"])
        return result
