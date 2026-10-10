
"""CarbonWise reporting for a scheduling decision."""

from monitoring.carbon_savings import compare_carbon_savings


def build_decision_report(evaluated_options, selected_option):
    """
    Compare the selected scheduling option with the run-now baseline.

    The report uses the scheduler's existing energy estimate and
    carbon-intensity forecast. Results are estimates, not measured
    real-world savings.
    """
    if not evaluated_options:
        raise ValueError("evaluated_options cannot be empty")

    baseline = next(
        (option for option in evaluated_options if option["delay"] == 0),
        None,
    )
    if baseline is None:
        raise ValueError("A run-now baseline with delay 0 is required")

    if selected_option not in evaluated_options:
        raise ValueError("selected_option must be one of evaluated_options")

    comparison = compare_carbon_savings(
        baseline_energy_kwh=baseline["energy_kwh"],
        baseline_intensity_g_per_kwh=baseline["carbon_intensity"],
        candidate_energy_kwh=selected_option["energy_kwh"],
        candidate_intensity_g_per_kwh=selected_option["carbon_intensity"],
        baseline_provenance="model_estimated",
        candidate_provenance="model_estimated",
    )

    return {
        "baseline_delay_minutes": baseline["delay"],
        "selected_delay_minutes": selected_option["delay"],
        "baseline_carbon_kg": comparison["baseline_emissions_kg"],
        "selected_carbon_kg": comparison["candidate_emissions_kg"],
        "predicted_savings_kg": comparison["carbon_savings_kg"],
        "predicted_savings_percent": comparison["carbon_savings_percent"],
        "evidence_status": comparison["evidence_status"],
        "savings_verified": comparison["savings_verified"],
    }
