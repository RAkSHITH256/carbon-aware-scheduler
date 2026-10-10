
"""Fairness and maximum-deferral policy for CarbonWise workloads."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class FairnessDecision:
    execute_now: bool
    effective_priority: float
    wait_minutes: float
    reason: str


def evaluate_fairness(
    *,
    base_priority: float,
    waited_minutes: float,
    proposed_delay_minutes: float,
    max_wait_minutes: float,
    deadline_minutes: float | None = None,
    aging_per_minute: float = 0.1,
) -> FairnessDecision:
    """Evaluate whether further deferral is fair and deadline-safe.

    Larger priority values represent higher priority. Aging increases
    effective priority as a workload waits. Maximum wait and deadline
    limits take precedence over carbon optimization.
    """

    values = {
        "base_priority": base_priority,
        "waited_minutes": waited_minutes,
        "proposed_delay_minutes": proposed_delay_minutes,
        "max_wait_minutes": max_wait_minutes,
        "aging_per_minute": aging_per_minute,
    }

    for name, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be a finite number")
        if not isfinite(value):
            raise ValueError(f"{name} must be a finite number")

    if any(value < 0 for value in values.values()):
        raise ValueError("Priority, wait, delay, and aging values must be non-negative")

    if deadline_minutes is not None:
        if (
            isinstance(deadline_minutes, bool)
            or not isinstance(deadline_minutes, (int, float))
            or not isfinite(deadline_minutes)
            or deadline_minutes < 0
        ):
            raise ValueError("deadline_minutes must be finite and non-negative")

    effective_priority = base_priority + waited_minutes * aging_per_minute
    projected_wait = waited_minutes + proposed_delay_minutes

    if waited_minutes >= max_wait_minutes:
        return FairnessDecision(
            execute_now=True,
            effective_priority=effective_priority,
            wait_minutes=0,
            reason="maximum_wait_reached",
        )

    if projected_wait > max_wait_minutes:
        return FairnessDecision(
            execute_now=True,
            effective_priority=effective_priority,
            wait_minutes=0,
            reason="delay_would_exceed_maximum_wait",
        )

    if (
        deadline_minutes is not None
        and projected_wait >= deadline_minutes
    ):
        return FairnessDecision(
            execute_now=True,
            effective_priority=effective_priority,
            wait_minutes=0,
            reason="deadline_protection",
        )

    return FairnessDecision(
        execute_now=False,
        effective_priority=effective_priority,
        wait_minutes=proposed_delay_minutes,
        reason="deferral_allowed",
    )
