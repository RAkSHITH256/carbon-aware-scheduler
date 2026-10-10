import csv
import os
from statistics import mean


FEEDBACK_FILE = "monitoring/execution_feedback.csv"

# Drift threshold
ENERGY_ERROR_THRESHOLD = 10.0
CARBON_ERROR_THRESHOLD = 10.0

# Number of recent executions used for drift detection
WINDOW_SIZE = 5


def load_recent_feedback():

    if not os.path.exists(FEEDBACK_FILE):
        return []

    with open(FEEDBACK_FILE, "r") as file:

        rows = list(csv.DictReader(file))

    return rows[-WINDOW_SIZE:]


def detect_drift():

    rows = load_recent_feedback()

    if not rows:
        return {
            "drift_detected": False,
            "reason": "No feedback data available",
            "samples": 0
        }

    energy_errors = []
    carbon_errors = []

    for row in rows:

        try:
            energy_errors.append(
                float(row["energy_error_percent"])
            )

            carbon_errors.append(
                float(row["carbon_error_percent"])
            )

        except (ValueError, KeyError):
            continue

    if not energy_errors or not carbon_errors:

        return {
            "drift_detected": False,
            "reason": "Insufficient valid feedback data",
            "samples": 0
        }

    avg_energy_error = mean(energy_errors)
    avg_carbon_error = mean(carbon_errors)

    drift_detected = (
        avg_energy_error > ENERGY_ERROR_THRESHOLD
        or avg_carbon_error > CARBON_ERROR_THRESHOLD
    )

    if drift_detected:
        reason = "Prediction error exceeded drift threshold"
    else:
        reason = "Prediction error within acceptable range"

    return {
        "drift_detected": drift_detected,
        "reason": reason,
        "samples": len(energy_errors),
        "average_energy_error_percent": avg_energy_error,
        "average_carbon_error_percent": avg_carbon_error,
        "energy_threshold_percent": ENERGY_ERROR_THRESHOLD,
        "carbon_threshold_percent": CARBON_ERROR_THRESHOLD
    }


if __name__ == "__main__":

    print("=" * 60)
    print("MLOPS DRIFT DETECTOR")
    print("=" * 60)

    result = detect_drift()

    print(f"Samples                 : {result['samples']}")
    print(
        f"Average energy error    : "
        f"{result.get('average_energy_error_percent', 0):.2f}%"
    )
    print(
        f"Average carbon error    : "
        f"{result.get('average_carbon_error_percent', 0):.2f}%"
    )

    print(
        f"Energy threshold        : "
        f"{result['energy_threshold_percent']:.2f}%"
    )

    print(
        f"Carbon threshold        : "
        f"{result['carbon_threshold_percent']:.2f}%"
    )

    print()

    if result["drift_detected"]:
        print("⚠ MODEL DRIFT DETECTED")
    else:
        print("✓ NO MODEL DRIFT DETECTED")

    print()
    print(f"Reason: {result['reason']}")
    print("=" * 60)
