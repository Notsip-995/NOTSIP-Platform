from __future__ import annotations
import json
import time
from dataclasses import dataclass


@dataclass
class WorkflowResult:
    status: str
    step: int
    total: int
    result: dict
    complete: bool = False


class WorkflowEngine:
    """Durable stepwise orchestration built on the existing scheduler and tool gate."""

    def __init__(self, agent, store):
        self.agent = agent
        self.store = store

    def normalize(self, steps):
        if not isinstance(steps, list) or not steps:
            raise ValueError("workflow steps must be a non-empty list")
        if len(steps) > 50:
            raise ValueError("workflow is limited to 50 steps")
        normalized = []
        for index, raw in enumerate(steps):
            if not isinstance(raw, dict):
                raise ValueError(f"workflow step {index + 1} must be an object")
            tool = str(raw.get("tool", "")).strip()
            if not tool:
                raise ValueError(f"workflow step {index + 1} requires a tool")
            args = raw.get("args") or {}
            if not isinstance(args, dict):
                raise ValueError(f"workflow step {index + 1} args must be an object")
            normalized.append({
                "id": str(raw.get("id") or index + 1),
                "tool": tool,
                "args": args,
                "depends_on": [str(x) for x in (raw.get("depends_on") or [])],
                "continue_on_failure": bool(raw.get("continue_on_failure", False)),
                "completion_statuses": list(raw.get("completion_statuses") or ["SUCCESS"]),
            })
        ids = {x["id"] for x in normalized}
        for step in normalized:
            if any(dep not in ids for dep in step["depends_on"]):
                raise ValueError(f"workflow step {step['id']} has an unknown dependency")
        return normalized

    async def run(self, task):
        data = task.get("data") or {}
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                data = {}
        steps = self.normalize(data.get("steps"))
        current = int(data.get("current_step", 0))
        results = list(data.get("step_results") or [])
        completed_ids = {str(x.get("id")) for x in results if x.get("status") in {"SUCCESS", "PARTIAL_SUCCESS"}}
        if current >= len(steps):
            return {"status": "SUCCESS", "workflow": {"complete": True, "steps": results}}

        step = steps[current]
        unmet = [dep for dep in step["depends_on"] if dep not in completed_ids]
        if unmet:
            data["current_step"] = current
            data["last_block"] = {"reason": "dependencies_unmet", "dependencies": unmet}
            self.store.task_update(task["id"], state="PENDING", run_at=time.time() + 1, data=json.dumps(data))
            return {"status": "PARTIAL_SUCCESS", "workflow": {"complete": False, "blocked": unmet, "step": step["id"]}}

        result = await self.agent.run_tool(step["tool"], step["args"])
        status = str(result.get("status", "UNKNOWN")) if isinstance(result, dict) else "UNKNOWN"
        results.append({"id": step["id"], "tool": step["tool"], "status": status, "result": result, "completed_at": time.time()})
        data["step_results"] = results

        accepted = status in set(step["completion_statuses"])
        if status == "PARTIAL_SUCCESS" and "PARTIAL_SUCCESS" in step["completion_statuses"]:
            accepted = True
        if not accepted:
            data["last_result"] = result
            if status in {"FAILURE", "UNKNOWN"} and not step["continue_on_failure"]:
                self.store.task_update(task["id"], state="UNKNOWN" if status == "UNKNOWN" else "FAILED", data=json.dumps(data), error=str(result.get("error", "workflow step failed")) if isinstance(result, dict) else "workflow step failed")
                return {"status": status, "workflow": {"complete": False, "step": step["id"], "result": result}}
        data["current_step"] = current + 1
        if current + 1 >= len(steps):
            data["completed_at"] = time.time()
            self.store.task_update(task["id"], state="COMPLETED", data=json.dumps(data), error="")
            return {"status": "SUCCESS", "workflow": {"complete": True, "steps": results}}
        self.store.task_update(task["id"], state="PENDING", run_at=time.time(), data=json.dumps(data), error="")
        return {"status": "CONTINUE", "workflow": {"complete": False, "next_step": steps[current + 1]["id"], "completed_step": step["id"], "result": result}}
