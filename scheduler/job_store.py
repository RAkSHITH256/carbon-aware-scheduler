
"""SQLite-backed persistent job state for CarbonWise."""

import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DB_PATH = (
    Path(__file__).resolve().parent.parent
    / "monitoring"
    / "carbonwise_jobs.sqlite3"
)

VALID_STATUSES = {
    "PENDING",
    "DEFERRED",
    "RUNNING",
    "COMPLETED",
    "FAILED",
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _validate_minutes(name, value, *, allow_zero=True):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
        or (not allow_zero and value == 0)
    ):
        raise ValueError(f"{name} must be a finite, non-negative number")


class JobStore:
    """Persistent job records with atomic SQLite state transitions."""

    def __init__(self, db_path=DEFAULT_DB_PATH):
        self.db_path = str(db_path)

        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(
                parents=True, exist_ok=True
            )

        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(
            self.db_path,
            timeout=10,
            isolation_level="DEFERRED",
        )
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    workload_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    submitted_at TEXT NOT NULL,
                    max_wait_minutes REAL NOT NULL,
                    deadline_minutes REAL,
                    recheck_count INTEGER NOT NULL DEFAULT 0,
                    next_recheck_at TEXT,
                    last_action TEXT,
                    last_reason TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    def create_job(
        self,
        *,
        job_id,
        workload_name,
        max_wait_minutes,
        deadline_minutes=None,
        metadata=None,
    ):
        """Create a new PENDING job; duplicate IDs are rejected."""

        if not isinstance(job_id, str) or not job_id.strip():
            raise ValueError("job_id must be a non-empty string")

        if (
            not isinstance(workload_name, str)
            or not workload_name.strip()
        ):
            raise ValueError("workload_name must be a non-empty string")

        _validate_minutes("max_wait_minutes", max_wait_minutes)

        if deadline_minutes is not None:
            _validate_minutes("deadline_minutes", deadline_minutes)

        if metadata is None:
            metadata = {}

        if not isinstance(metadata, dict):
            raise ValueError("metadata must be a dictionary")

        metadata_json = json.dumps(metadata, allow_nan=False)
        now = _now()

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    job_id, workload_name, status, submitted_at,
                    max_wait_minutes, deadline_minutes,
                    metadata_json, updated_at
                )
                VALUES (?, ?, 'PENDING', ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    workload_name,
                    now,
                    float(max_wait_minutes),
                    (
                        float(deadline_minutes)
                        if deadline_minutes is not None
                        else None
                    ),
                    metadata_json,
                    now,
                ),
            )

        return self.get_job(job_id)

    def get_job(self, job_id):
        """Return one job as a dictionary, or None if it does not exist."""

        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()

        if row is None:
            return None

        result = dict(row)
        result["metadata"] = json.loads(result.pop("metadata_json"))
        return result

    def list_jobs(self, *, status=None):
        """List jobs ordered by submission time."""

        if status is not None and status not in VALID_STATUSES:
            raise ValueError("Invalid job status")

        with self._connect() as connection:
            if status is None:
                rows = connection.execute(
                    "SELECT * FROM jobs ORDER BY submitted_at, job_id"
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM jobs
                    WHERE status = ?
                    ORDER BY submitted_at, job_id
                    """,
                    (status,),
                ).fetchall()

        results = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json"))
            results.append(item)

        return results

    def record_recheck(
        self,
        job_id,
        *,
        action,
        reason,
        next_recheck_at=None,
    ):
        """Persist a scheduler recheck without submitting a workload."""

        if action not in {"RUN_NOW", "DEFER"}:
            raise ValueError("action must be RUN_NOW or DEFER")

        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be a non-empty string")

        now = _now()

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET recheck_count = recheck_count + 1,
                    last_action = ?,
                    last_reason = ?,
                    next_recheck_at = ?,
                    updated_at = ?,
                    version = version + 1
                WHERE job_id = ?
                  AND status IN ('PENDING', 'DEFERRED')
                """,
                (
                    action,
                    reason,
                    next_recheck_at,
                    now,
                    job_id,
                ),
            )

            if cursor.rowcount != 1:
                existing = connection.execute(
                    "SELECT status FROM jobs WHERE job_id = ?",
                    (job_id,),
                ).fetchone()

                if existing is None:
                    raise KeyError(f"Unknown job_id: {job_id}")

                raise ValueError(
                    f"Cannot recheck job in status {existing['status']}"
                )

        return self.get_job(job_id)

    def claim_job(self, job_id):
        """Atomically claim a pending/deferred job for execution.

        Returns True only when this call changes its status to RUNNING.
        This claim does not itself submit a Kubernetes Job.
        """

        now = _now()

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status = 'RUNNING',
                    updated_at = ?,
                    version = version + 1
                WHERE job_id = ?
                  AND status IN ('PENDING', 'DEFERRED')
                """,
                (now, job_id),
            )

            if cursor.rowcount == 1:
                return True

            existing = connection.execute(
                "SELECT job_id FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()

            if existing is None:
                raise KeyError(f"Unknown job_id: {job_id}")

            return False

    def set_deferred(self, job_id, *, next_recheck_at, reason):
        """Move an unclaimed job to DEFERRED."""

        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be a non-empty string")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status = 'DEFERRED',
                    next_recheck_at = ?,
                    last_action = 'DEFER',
                    last_reason = ?,
                    updated_at = ?,
                    version = version + 1
                WHERE job_id = ?
                  AND status IN ('PENDING', 'DEFERRED')
                """,
                (next_recheck_at, reason, _now(), job_id),
            )

            if cursor.rowcount != 1:
                existing = connection.execute(
                    "SELECT status FROM jobs WHERE job_id = ?",
                    (job_id,),
                ).fetchone()

                if existing is None:
                    raise KeyError(f"Unknown job_id: {job_id}")

                raise ValueError(
                    f"Cannot defer job in status {existing['status']}"
                )

        return self.get_job(job_id)

    def complete_job(self, job_id):
        """Mark a RUNNING job as COMPLETED."""

        return self._finish(job_id, "COMPLETED")

    def fail_job(self, job_id, *, reason):
        """Mark a RUNNING job as FAILED."""

        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be a non-empty string")

        return self._finish(job_id, "FAILED", reason=reason)

    def _finish(self, job_id, status, *, reason=None):
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status = ?,
                    last_reason = COALESCE(?, last_reason),
                    updated_at = ?,
                    version = version + 1
                WHERE job_id = ? AND status = 'RUNNING'
                """,
                (status, reason, _now(), job_id),
            )

            if cursor.rowcount != 1:
                existing = connection.execute(
                    "SELECT status FROM jobs WHERE job_id = ?",
                    (job_id,),
                ).fetchone()

                if existing is None:
                    raise KeyError(f"Unknown job_id: {job_id}")

                raise ValueError(
                    f"Cannot finish job in status {existing['status']}"
                )

        return self.get_job(job_id)
