
import pytest

from scheduler.recheck import decide_after_recheck


def test_defers_when_carbon_is_lower_and_wait_is_allowed():
    result = decide_after_recheck(
        current_carbon_intensity=600,
        proposed_carbon_intensity=500,
        waited_minutes=10,
        proposed_delay_minutes=15,
        max_wait_minutes=60,
        deadline_minutes=120,
    )

    assert result.action == "DEFER"
    assert result.remaining_wait_minutes == 15
    assert result.reason == "lower_carbon_forecast_and_fairness_allows"


def test_runs_when_forecast_is_not_better():
    result = decide_after_recheck(
        current_carbon_intensity=500,
        proposed_carbon_intensity=600,
        waited_minutes=0,
        proposed_delay_minutes=15,
        max_wait_minutes=60,
    )

    assert result.action == "RUN_NOW"
    assert result.reason == "forecast_not_improved"


def test_maximum_wait_overrides_carbon_optimization():
    result = decide_after_recheck(
        current_carbon_intensity=600,
        proposed_carbon_intensity=400,
        waited_minutes=60,
        proposed_delay_minutes=15,
        max_wait_minutes=60,
    )

    assert result.action == "RUN_NOW"
    assert result.reason == "maximum_wait_reached"


def test_deadline_protection_overrides_carbon_optimization():
    result = decide_after_recheck(
        current_carbon_intensity=600,
        proposed_carbon_intensity=400,
        waited_minutes=10,
        proposed_delay_minutes=20,
        max_wait_minutes=60,
        deadline_minutes=30,
    )

    assert result.action == "RUN_NOW"
    assert result.reason == "deadline_protection"


@pytest.mark.parametrize(
    "field,value",
    [
        ("current_carbon_intensity", -1),
        ("proposed_carbon_intensity", float("nan")),
        ("proposed_carbon_intensity", float("inf")),
        ("current_carbon_intensity", True),
    ],
)
def test_invalid_carbon_values_are_rejected(field, value):
    kwargs = {
        "current_carbon_intensity": 600,
        "proposed_carbon_intensity": 500,
        "waited_minutes": 0,
        "proposed_delay_minutes": 15,
        "max_wait_minutes": 60,
    }
    kwargs[field] = value

    with pytest.raises(ValueError):
        decide_after_recheck(**kwargs)
