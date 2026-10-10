import csv
import os
from datetime import datetime


FEEDBACK_FILE = "monitoring/execution_feedback.csv"


def record_execution(
    job_name,
    predicted_energy_kwh,
    actual_energy_kwh,
    predicted_carbon_kg,
    actual_carbon_kg,
    runtime_seconds
):
    """
    Record actual vs predicted execution results.
    """

    predicted_energy_error = (
        abs(actual_energy_kwh - predicted_energy_kwh)
        / predicted_energy_kwh
        * 100
        if predicted_energy_kwh > 0
        else 0
    )

    predicted_carbon_error = (
        abs(actual_carbon_kg - predicted_carbon_kg)
        / predicted_carbon_kg
        * 100
        if predicted_carbon_kg > 0
        else 0
    )

    file_exists = os.path.exists(FEEDBACK_FILE)

    with open(FEEDBACK_FILE, "a", newline="") as file:

        writer = csv.writer(file)

        if not file_exists:
            writer.writerow([
                "timestamp",
                "job_name",
                "predicted_energy_kwh",
                "actual_energy_kwh",
                "energy_error_percent",
                "predicted_carbon_kg",
                "actual_carbon_kg",
                "carbon_error_percent",
                "runtime_seconds"
            ])

        writer.writerow([
            datetime.utcnow().isoformat(),
            job_name,
            predicted_energy_kwh,
            actual_energy_kwh,
            predicted_energy_error,
            predicted_carbon_kg,
            actual_carbon_kg,
            predicted_carbon_error,
            runtime_seconds
        ])

    return {
        "job_name": job_name,
        "energy_error_percent": predicted_energy_error,
        "carbon_error_percent": predicted_carbon_error,
        "runtime_seconds": runtime_seconds
    }
