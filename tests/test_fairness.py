
import pytest

from scheduler.fairness import evaluate_fairness


def test_deferral_allowed_within_limits():
    result = evaluate_fairness(
        base_priority=1,
        waited_minutes=5,
        proposed_delay_minutes=10,
        max_wait_minutes=60,
        deadline_minutes=120,
    )

    assert not result.execute_now
    assert result.wait_minutes == 10
    assert result.reason == "deferral_allowed"


def test_aging_increases_priority():
    result = evaluate_fairness(
        base_priority=1,
        waited_minutes=20,
        proposed_delay_minutes=5,
        max_wait_minutes=60,
        aging_per_minute=0.1,
    )

    assert result.effective_priority == pytest.approx(3.0)


def test_execute_when_maximum_wait_reached():
    result = evaluate_fairness(
        base_priority=1,
        waited_minutes=60,
        proposed_delay_minutes=10,
        max_wait_minutes=60,
    )

    assert result.execute_now
    assert result.reason == "maximum_wait_reached"


def test_execute_when_delay_exceeds_maximum_wait():
    result = evaluate_fairness(
        base_priority=1,
        waited_minutes=55,
        proposed_delay_minutes=10,
        max_wait_minutes=60,
    )

    assert result.execute_now
    assert result.reason == "delay_would_exceed_maximum_wait"


def test_deadline_protection():
    result = evaluate_fairness(
        base_priority=1,
        waited_minutes=10,
        proposed_delay_minutes=20,
        max_wait_minutes=60,
        deadline_minutes=30,
    )

    assert result.execute_now
    assert result.reason == "deadline_protection"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"waited_minutes": -1},
        {"proposed_delay_minutes": -1},
        {"max_wait_minutes": -1},
        {"aging_per_minute": float("nan")},
    ],
)
def test_invalid_fairness_inputs_are_rejected(kwargs):
    values = {
        "base_priority": 1,
        "waited_minutes": 0,
        "proposed_delay_minutes": 5,
        "max_wait_minutes": 60,
    }
    values.update(kwargs)

    with pytest.raises(ValueError):
        evaluate_fairness(**values)
