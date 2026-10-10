
import pytest

from scheduler.job_store import JobStore


@pytest.fixture
def store(tmp_path):
    return JobStore(tmp_path / "test_jobs.sqlite3")


def create_test_job(store, job_id="job-001"):
    return store.create_job(
        job_id=job_id,
        workload_name="test-workload",
        max_wait_minutes=30,
        deadline_minutes=60,
        metadata={"environment": "test"},
    )


def test_create_and_retrieve_job(store):
    created = create_test_job(store)

    assert created["job_id"] == "job-001"
    assert created["status"] == "PENDING"
    assert created["max_wait_minutes"] == 30
    assert created["metadata"] == {"environment": "test"}


def test_persistence_across_store_instances(tmp_path):
    db_path = tmp_path / "persistent.sqlite3"

    first = JobStore(db_path)
    create_test_job(first)

    second = JobStore(db_path)

    assert second.get_job("job-001")["status"] == "PENDING"


def test_duplicate_job_id_is_rejected(store):
    create_test_job(store)

    with pytest.raises(Exception):
        create_test_job(store)


def test_recheck_is_recorded(store):
    create_test_job(store)

    job = store.record_recheck(
        "job-001",
        action="DEFER",
        reason="lower_carbon_forecast",
        next_recheck_at="2030-01-01T00:00:00+00:00",
    )

    assert job["recheck_count"] == 1
    assert job["last_action"] == "DEFER"
    assert job["last_reason"] == "lower_carbon_forecast"


def test_claim_succeeds_only_once(store):
    create_test_job(store)

    assert store.claim_job("job-001") is True
    assert store.claim_job("job-001") is False

    assert store.get_job("job-001")["status"] == "RUNNING"


def test_complete_requires_running_job(store):
    create_test_job(store)

    with pytest.raises(ValueError):
        store.complete_job("job-001")

    store.claim_job("job-001")

    assert store.complete_job("job-001")["status"] == "COMPLETED"


def test_failed_job_records_reason(store):
    create_test_job(store)
    store.claim_job("job-001")

    job = store.fail_job(
        "job-001",
        reason="test execution failure",
    )

    assert job["status"] == "FAILED"
    assert job["last_reason"] == "test execution failure"


def test_invalid_job_inputs_are_rejected(store):
    with pytest.raises(ValueError):
        create_test_job(store, job_id="")

    with pytest.raises(ValueError):
        store.create_job(
            job_id="bad-delay",
            workload_name="test",
            max_wait_minutes=float("nan"),
        )


def test_recheck_unknown_job_is_rejected(store):
    with pytest.raises(KeyError):
        store.record_recheck(
            "missing-job",
            action="DEFER",
            reason="test",
        )


def test_list_jobs_can_filter_by_status(store):
    create_test_job(store, "job-pending")
    create_test_job(store, "job-running")
    store.claim_job("job-running")

    pending = store.list_jobs(status="PENDING")
    running = store.list_jobs(status="RUNNING")

    assert [job["job_id"] for job in pending] == ["job-pending"]
    assert [job["job_id"] for job in running] == ["job-running"]
