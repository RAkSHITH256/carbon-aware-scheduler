import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend import main
from monitoring.decision_audit import write_decision_audit


def make_workload():
    return SimpleNamespace(
        cpu_utilization=50.0,
        memory_utilization=60.0,
        gpu_utilization=0.0,
        runtime_hours=1.0,
        idle_power_w=20.0,
        max_power_w=100.0,
        cost_per_hour=100.0,
        carbon_budget_kg=0.5,
        max_delay_minutes=60,
    )


def make_option(delay=60):
    return {
        "delay": delay,
        "carbon_intensity": 575.8,
        "energy_kwh": 0.0267,
        "carbon_kg": 0.0154,
        "cost": 100.0,
        "score": 0.2,
        "budget_ok": True,
        "budget_feasible": True,
        "budget_status": "satisfied",
        "forecast_status": "available",
    }


def make_savings_report():
    return {
        "baseline_delay_minutes": 0,
        "selected_delay_minutes": 60,
        "baseline_carbon_kg": 0.0158,
        "selected_carbon_kg": 0.0154,
        "predicted_savings_kg": 0.0004,
        "predicted_savings_percent": 2.5,
        "evidence_status": "estimate_or_simulation",
        "savings_verified": False,
    }


def test_audit_writes_valid_jsonl_record(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    workload = make_workload()
    options = [make_option(0), make_option(60)]
    selected = options[1]

    record = write_decision_audit(
        workload=workload,
        evaluated_options=options,
        selected_option=selected,
        current_carbon_intensity=592.8,
        carbon_savings_report=make_savings_report(),
        audit_path=audit_path,
    )

    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    persisted = json.loads(lines[0])
    assert persisted["event"] == "carbonwise_scheduling_decision"
    assert persisted["decision_id"] == record["decision_id"]
    assert persisted["selected_option"]["delay_minutes"] == 60
    assert len(persisted["candidate_options"]) == 2
    assert persisted["current_carbon_intensity_gco2_kwh"] == 592.8


def test_audit_has_unique_decision_ids(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    workload = make_workload()
    option = make_option()

    kwargs = {
        "workload": workload,
        "evaluated_options": [option],
        "selected_option": option,
        "current_carbon_intensity": 592.8,
        "carbon_savings_report": make_savings_report(),
        "audit_path": audit_path,
    }

    first = write_decision_audit(**kwargs)
    second = write_decision_audit(**kwargs)

    records = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
    ]

    assert len(records) == 2
    assert first["decision_id"] != second["decision_id"]
    assert records[0]["decision_id"] != records[1]["decision_id"]


def test_audit_timestamp_is_valid_utc_datetime(tmp_path):
    record = write_decision_audit(
        workload=make_workload(),
        evaluated_options=[make_option()],
        selected_option=make_option(),
        current_carbon_intensity=592.8,
        carbon_savings_report=make_savings_report(),
        audit_path=tmp_path / "audit.jsonl",
    )

    timestamp = datetime.fromisoformat(record["timestamp_utc"])
    assert timestamp.tzinfo is not None
    assert timestamp.utcoffset().total_seconds() == 0


def test_audit_marks_savings_as_unverified(tmp_path):
    record = write_decision_audit(
        workload=make_workload(),
        evaluated_options=[make_option()],
        selected_option=make_option(),
        current_carbon_intensity=592.8,
        carbon_savings_report=make_savings_report(),
        audit_path=tmp_path / "audit.jsonl",
    )

    assert record["evidence_status"] == "estimate_or_simulation"
    assert record["savings_verified"] is False
    assert record["carbon_savings_report"]["savings_verified"] is False


def test_audit_rejects_empty_candidate_options(tmp_path):
    with pytest.raises(ValueError, match="evaluated_options cannot be empty"):
        write_decision_audit(
            workload=make_workload(),
            evaluated_options=[],
            selected_option=make_option(),
            current_carbon_intensity=592.8,
            carbon_savings_report=make_savings_report(),
            audit_path=tmp_path / "audit.jsonl",
        )

    assert not (tmp_path / "audit.jsonl").exists()


def test_audit_rejects_unselected_candidate(tmp_path):
    with pytest.raises(ValueError, match="selected_option must be in evaluated_options"):
        write_decision_audit(
            workload=make_workload(),
            evaluated_options=[make_option(0)],
            selected_option=make_option(60),
            current_carbon_intensity=592.8,
            carbon_savings_report=make_savings_report(),
            audit_path=tmp_path / "audit.jsonl",
        )

    assert not (tmp_path / "audit.jsonl").exists()


def test_schedule_api_persists_matching_audit_record(tmp_path, monkeypatch):
    audit_path = tmp_path / "api-audit.jsonl"
    options = [make_option(0), make_option(60)]
    selected = options[1]

    def fake_choose_schedule(workload, current_carbon_intensity):
        return options, selected

    def fake_build_report(evaluated_options, selected_option):
        return make_savings_report()

    real_writer = write_decision_audit

    def temporary_audit_writer(**kwargs):
        return real_writer(**kwargs, audit_path=audit_path)

    monkeypatch.setattr(main, "choose_schedule", fake_choose_schedule)
    monkeypatch.setattr(main, "build_decision_report", fake_build_report)
    monkeypatch.setattr(main, "write_decision_audit", temporary_audit_writer)

    client = TestClient(main.app)
    response = client.post(
        "/schedule",
        json={
            "cpu_utilization": 50,
            "memory_utilization": 60,
            "gpu_utilization": 0,
            "runtime_hours": 1,
            "idle_power_w": 20,
            "max_power_w": 100,
            "cost_per_hour": 100,
            "carbon_budget_kg": 0.5,
            "max_delay_minutes": 60,
            "current_carbon_intensity": 592.8,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"] == "WAIT_60_MINUTES"
    assert payload["decision_id"]

    records = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 1
    assert records[0]["decision_id"] == payload["decision_id"]
    assert records[0]["selected_option"]["delay_minutes"] == 60
    assert records[0]["savings_verified"] is False


def test_schedule_api_rejects_invalid_request():
    client = TestClient(main.app)
    payload = make_api_payload()
    payload["cpu_utilization"] = 150

    response = client.post("/schedule", json=payload)

    assert response.status_code == 422


def test_schedule_api_returns_server_error_if_scheduler_fails(monkeypatch):
    def fail_scheduler(workload, current_carbon_intensity):
        raise RuntimeError("simulated scheduler failure")

    monkeypatch.setattr(main, "choose_schedule", fail_scheduler)
    client = TestClient(main.app, raise_server_exceptions=False)

    response = client.post("/schedule", json=make_api_payload())

    assert response.status_code == 500


def test_schedule_api_does_not_execute_if_audit_write_fails(monkeypatch):
    options = [make_option(0)]
    selected = options[0]

    def fake_choose_schedule(workload, current_carbon_intensity):
        return options, selected

    def fake_build_report(evaluated_options, selected_option):
        return make_savings_report()

    def fail_audit_writer(**kwargs):
        raise OSError("simulated audit storage failure")

    def unexpected_execution():
        pytest.fail("Workload executed despite audit failure")

    monkeypatch.setattr(main, "choose_schedule", fake_choose_schedule)
    monkeypatch.setattr(main, "build_decision_report", fake_build_report)
    monkeypatch.setattr(main, "write_decision_audit", fail_audit_writer)
    monkeypatch.setattr(main, "execute_workload", unexpected_execution)

    client = TestClient(main.app, raise_server_exceptions=False)
    response = client.post("/schedule", json=make_api_payload())

    assert response.status_code == 500


def make_api_payload():
    return {
        "cpu_utilization": 50,
        "memory_utilization": 60,
        "gpu_utilization": 0,
        "runtime_hours": 1,
        "idle_power_w": 20,
        "max_power_w": 100,
        "cost_per_hour": 100,
        "carbon_budget_kg": 0.5,
        "max_delay_minutes": 60,
        "current_carbon_intensity": 592.8,
    }
