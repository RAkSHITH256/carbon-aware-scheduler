
"""
CarbonWise Verified Carbon Savings Engine.

Carbon intensity is expressed in gCO2e/kWh.
Energy is expressed in kWh.
Emissions are expressed in kgCO2e.

Savings are estimates unless the evidence is sufficient
to classify the comparison as measured.
"""

from math import isfinite


VALID_PROVENANCE = {
    "measured",
    "model_estimated",
    "derived",
    "simulated",
}


def _validate_nonnegative(value, field_name):
    """Validate a finite, non-negative numeric input."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number")

    if not isfinite(value) or value < 0:
        raise ValueError(
            f"{field_name} must be finite and non-negative"
        )


def _validate_provenance(provenance, field_name):
    if provenance not in VALID_PROVENANCE:
        raise ValueError(
            f"{field_name} must be one of "
            f"{sorted(VALID_PROVENANCE)}"
        )


def calculate_emissions_kg(energy_kwh, intensity_g_per_kwh):
    """Calculate CO2e emissions from energy and grid intensity."""
    _validate_nonnegative(energy_kwh, "energy_kwh")
    _validate_nonnegative(
        intensity_g_per_kwh,
        "intensity_g_per_kwh",
    )

    return energy_kwh * intensity_g_per_kwh / 1000.0


def compare_carbon_savings(
    baseline_energy_kwh,
    baseline_intensity_g_per_kwh,
    candidate_energy_kwh,
    candidate_intensity_g_per_kwh,
    baseline_provenance="model_estimated",
    candidate_provenance="model_estimated",
):
    """
    Compare a baseline with a candidate scheduling decision.

    Positive savings mean lower candidate emissions.
    Negative savings mean the candidate emitted more.

    'measured' means the supplied emissions inputs are classified
    as measured by the caller; this function cannot verify sensors
    or the authenticity of their data.
    """
    _validate_provenance(
        baseline_provenance,
        "baseline_provenance",
    )
    _validate_provenance(
        candidate_provenance,
        "candidate_provenance",
    )

    baseline_kg = calculate_emissions_kg(
        baseline_energy_kwh,
        baseline_intensity_g_per_kwh,
    )
    candidate_kg = calculate_emissions_kg(
        candidate_energy_kwh,
        candidate_intensity_g_per_kwh,
    )

    savings_kg = baseline_kg - candidate_kg

    savings_percent = (
        (savings_kg / baseline_kg) * 100.0
        if baseline_kg > 0
        else None
    )

    verified = (
        baseline_provenance == "measured"
        and candidate_provenance == "measured"
    )

    return {
        "baseline_emissions_kg": baseline_kg,
        "candidate_emissions_kg": candidate_kg,
        "carbon_savings_kg": savings_kg,
        "carbon_savings_percent": savings_percent,
        "baseline_provenance": baseline_provenance,
        "candidate_provenance": candidate_provenance,
        "evidence_status": (
            "measured_comparison" if verified
            else "estimate_or_simulation"
        ),
        "savings_verified": verified,
    }
