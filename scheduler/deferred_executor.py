"""Deferred execution with explicit production and test timing."""

import math
import time
from datetime import datetime

from backend.execution import execute_workload


def execute_after_delay(
    delay_minutes,
    workload_name="carbon-aware-workload",
    *,
    test_mode=False,
    sleep_fn=None,
):
    """Wait for the selected delay, then submit a Kubernetes Job."""

    if (
        isinstance(delay_minutes, bool)
        or not isinstance(delay_minutes, (int, float))
        or not math.isfinite(delay_minutes)
        or delay_minutes < 0
    ):
        raise ValueError("delay_minutes must be a finite, non-negative number")

    sleeper = sleep_fn if sleep_fn is not None else time.sleep
    delay_seconds = delay_minutes if test_mode else delay_minutes * 60

    print("=" * 60)
    print("DEFERRED CARBON-AWARE EXECUTION")
    print("=" * 60)
    print(f"Workload : {workload_name}")
    print(f"Delay    : {delay_minutes} minutes")
    print(f"Started  : {datetime.now()}")

    if delay_seconds > 0:
        print(f"Waiting {delay_seconds} seconds...")
        sleeper(delay_seconds)

    print("Scheduling window reached.")
    print("Launching Kubernetes workload...")

    job_name = execute_workload()

    print(f"Kubernetes Job : {job_name}")
    print(f"Executed       : {datetime.now()}")
    print("=" * 60)

    return job_name


if __name__ == "__main__":
    job_name = execute_after_delay(delay_minutes=5)
    print(f"Created Job: {job_name}")