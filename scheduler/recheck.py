
"""Carbon rechecking and fairness-aware execution decisions."""

from dataclasses import dataclass
from math import isfinite

from ml.carbon_predict import predict_future_carbon
from scheduler.fairness import evaluate_fairness


@dataclass(frozen=True)
class RecheckDecision:
    action: str
    carbon_intensity: float
    effective_priority: float
    remaining_wait_minutes: float
    reason: str


def recheck_carbon():
    """Return the next predicted carbon intensity."""

    prediction = predict_future_carbon(1)

    if not prediction:
        raise ValueError("Carbon forecast returned no predictions")

    carbon_intensity = prediction[0]

    if (
        isinstance(carbon_intensity, bool)
        or not isinstance(carbon_intensity, (int, float))
        or not isfinite(carbon_intensity)
        or carbon_intensity < 0
    ):
        raise ValueError(
            "Carbon forecast must be finite and non-negative"
        )

    print("=" * 60)
    print("CARBON RE-CHECK")
    print(
        f"Predicted carbon intensity: "
        f"{carbon_intensity:.2f} gCO2/kWh"
    )
    print("=" * 60)

    return float(carbon_intensity)


def decide_after_recheck(
    *,
    current_carbon_intensity,
    proposed_carbon_intensity,
    waited_minutes,
    proposed_delay_minutes,
    max_wait_minutes,
    base_priority=1.0,
    deadline_minutes=None,
    aging_per_minute=0.1,
):
    """Choose RUN_NOW or DEFER using forecast and fairness constraints.

    Carbon intensity values must use the same units. This function
    returns a recommendation and never submits a Kubernetes Job.
    """

    for name, value in (
        ("current_carbon_intensity", current_carbon_intensity),
        ("proposed_carbon_intensity", proposed_carbon_intensity),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
            or value < 0
        ):
            raise ValueError(
                f"{name} must be finite and non-negative"
            )

    fairness = evaluate_fairness(
        base_priority=base_priority,
        waited_minutes=waited_minutes,
        proposed_delay_minutes=proposed_delay_minutes,
        max_wait_minutes=max_wait_minutes,
        deadline_minutes=deadline_minutes,
        aging_per_minute=aging_per_minute,
    )

    if fairness.execute_now:
        action = "RUN_NOW"
        reason = fairness.reason
        remaining_wait = 0.0
    elif proposed_carbon_intensity < current_carbon_intensity:
        action = "DEFER"
        reason = "lower_carbon_forecast_and_fairness_allows"
        remaining_wait = fairness.wait_minutes
    else:
        action = "RUN_NOW"
        reason = "forecast_not_improved"

        # No additional deferral is recommended.
        remaining_wait = 0.0

    return RecheckDecision(
        action=action,
        carbon_intensity=float(proposed_carbon_intensity),
        effective_priority=fairness.effective_priority,
        remaining_wait_minutes=remaining_wait,
        reason=reason,
    )
