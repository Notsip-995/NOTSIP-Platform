from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum

class Priority(IntEnum):
    IGNORE = 0
    BACKGROUND = 1
    RELEVANT = 2
    IMPORTANT = 3
    URGENT = 4
    CRITICAL = 5

@dataclass(frozen=True)
class PriorityDecision:
    priority: Priority
    interrupt: bool
    score: float
    reason: str

class EventPriorityEngine:
    """Deterministic event triage before proactive interruption."""
    def __init__(self, threshold: int = Priority.IMPORTANT, critical_interrupt: bool = True):
        self.threshold = Priority(max(Priority.IGNORE, min(Priority.CRITICAL, int(threshold))))
        self.critical_interrupt = bool(critical_interrupt)

    def classify(self, *, importance: float = 0.0, urgency: float = 0.0, relevance: float = 0.0,
                 explicit_interrupt: bool = False, event_type: str = "") -> PriorityDecision:
        values = [max(0.0, min(1.0, float(x))) for x in (importance, urgency, relevance)]
        score = 0.4 * values[0] + 0.35 * values[1] + 0.25 * values[2]
        if explicit_interrupt:
            score = max(score, 0.9)
        if values[1] >= 0.95 and values[2] >= 0.7:
            priority = Priority.CRITICAL
        elif score >= 0.82:
            priority = Priority.URGENT
        elif score >= 0.62:
            priority = Priority.IMPORTANT
        elif score >= 0.38:
            priority = Priority.RELEVANT
        elif score >= 0.12:
            priority = Priority.BACKGROUND
        else:
            priority = Priority.IGNORE
        interrupt = priority >= self.threshold and (priority == Priority.CRITICAL and self.critical_interrupt or priority != Priority.CRITICAL)
        reason = f"{event_type or 'event'} classified {priority.name.lower()} (score={score:.2f})"
        return PriorityDecision(priority, interrupt, score, reason)
