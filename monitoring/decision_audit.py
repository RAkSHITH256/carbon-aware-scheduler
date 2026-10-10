
"""Append-only JSONL audit records for CarbonWise scheduling decisions."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4


DEFAULT_AUDIT_PATH = Path(__file__).resolve().parent / "decision_audit.jsonl"
_AUDIT_LOCK = Lock()


def write_decision_audit(
    workload,
    evaluated_options,
    selected_option,
    current_carbon_intensity,
    carbon_savings_report,
    audit_path=None,
):
    """
    Append one JSON audit record.

    Carbon and savings values are model estimates unless independently
    verified by a separate measurement process.
    """
    if not evaluated_options:
        raise ValueError("evaluated_options cannot be empty")

    if selected_option not in evaluated_options:
        raise ValueError("selected_option must be in evaluated_options")

    path = Path(audit_path) if audit_path else DEFAULT_AUDIT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "event": "carbonwise_scheduling_decision",
        "decision_id": str(uuid4()),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "workload": {
            "cpu_utilization": workload.cpu_utilization,
            "memory_utilization": workload.memory_utilization,
            "gpu_utilization": workload.gpu_utilization,
            "runtime_hours": workload.runtime_hours,
            "idle_power_w": workload.idle_power_w,
            "max_power_w": workload.max_power_w,
            "cost_per_hour": workload.cost_per_hour,
            "carbon_budget_kg": workload.carbon_budget_kg,
            "max_delay_minutes": workload.max_delay_minutes,
        },
        "current_carbon_intensity_gco2_kwh": float(
            current_carbon_intensity
        ),
        "forecast_status": selected_option.get(
            "forecast_status", "not_reported"
        ),
        "selected_option": {
            "delay_minutes": selected_option["delay"],
            "carbon_intensity_gco2_kwh": selected_option["carbon_intensity"],
            "energy_kwh": selected_option["energy_kwh"],
            "estimated_carbon_kg": selected_option["carbon_kg"],
            "estimated_cost": selected_option["cost"],
            "optimization_score": selected_option.get("score"),
            "budget_ok": selected_option["budget_ok"],
            "budget_feasible": selected_option.get("budget_feasible"),
            "budget_status": selected_option.get("budget_status"),
        },
        "candidate_options": [
            {
                "delay_minutes": option["delay"],
                "carbon_intensity_gco2_kwh": option["carbon_intensity"],
                "energy_kwh": option["energy_kwh"],
                "estimated_carbon_kg": option["carbon_kg"],
                "estimated_cost": option["cost"],
                "optimization_score": option.get("score"),
                "budget_ok": option["budget_ok"],
            }
            for option in evaluated_options
        ],
        "carbon_savings_report": carbon_savings_report,
        "evidence_status": "estimate_or_simulation",
        "savings_verified": False,
    }

    # Prevent concurrent requests from interleaving JSON records.
    with _AUDIT_LOCK:
        with path.open("a", encoding="utf-8") as file:
            file.write(
                json.dumps(record, allow_nan=False, separators=(",", ":"))
                + "\n"
            )

    return record
