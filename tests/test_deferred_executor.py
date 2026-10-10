
import pytest

from scheduler import deferred_executor


def test_production_delay_is_converted_to_seconds(monkeypatch):
    sleeps = []
    monkeypatch.setattr(
        deferred_executor,
        "execute_workload",
        lambda: "test-job",
    )

    result = deferred_executor.execute_after_delay(
        5,
        sleep_fn=sleeps.append,
    )

    assert sleeps == [300]
    assert result == "test-job"


def test_test_mode_uses_seconds(monkeypatch):
    sleeps = []
    monkeypatch.setattr(
        deferred_executor,
        "execute_workload",
        lambda: "test-job",
    )

    deferred_executor.execute_after_delay(
        5,
        test_mode=True,
        sleep_fn=sleeps.append,
    )

    assert sleeps == [5]


@pytest.mark.parametrize("delay", [-1, float("nan"), float("inf"), True])
def test_invalid_delay_is_rejected(delay):
    with pytest.raises(ValueError):
        deferred_executor.execute_after_delay(
            delay,
            sleep_fn=lambda seconds: None,
        )


def test_zero_delay_does_not_sleep(monkeypatch):
    sleeps = []
    monkeypatch.setattr(
        deferred_executor,
        "execute_workload",
        lambda: "immediate-job",
    )

    result = deferred_executor.execute_after_delay(
        0,
        sleep_fn=sleeps.append,
    )

    assert sleeps == []
    assert result == "immediate-job"
