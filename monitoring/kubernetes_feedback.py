from datetime import datetime, timezone
from kubernetes import client, config


NAMESPACE = "default"


def wait_for_job(job_name, poll_interval=2):

    config.load_kube_config()

    batch_api = client.BatchV1Api()
    core_api = client.CoreV1Api()

    print(f"Monitoring Job: {job_name}")

    while True:

        job = batch_api.read_namespaced_job_status(
            name=job_name,
            namespace=NAMESPACE
        )

        if job.status.succeeded and job.status.succeeded >= 1:
            status = "Complete"
            break

        if job.status.failed and job.status.failed >= 1:
            status = "Failed"
            break

        import time
        time.sleep(poll_interval)

    # Find the Pod created by this Job
    pods = core_api.list_namespaced_pod(
        namespace=NAMESPACE,
        label_selector=f"job-name={job_name}"
    )

    if not pods.items:
        return {
            "job_name": job_name,
            "status": status,
            "runtime_seconds": None
        }

    pod = pods.items[0]

    start_time = None
    finish_time = None

    for container_status in pod.status.container_statuses or []:

        state = container_status.state

        if state.terminated:

            start_time = state.terminated.started_at
            finish_time = state.terminated.finished_at

            break

    if start_time and finish_time:

        runtime_seconds = (
            finish_time - start_time
        ).total_seconds()

    else:
        runtime_seconds = None

    return {
        "job_name": job_name,
        "status": status,
        "runtime_seconds": runtime_seconds,
        "started_at": start_time,
        "finished_at": finish_time
    }


if __name__ == "__main__":

    import sys

    if len(sys.argv) != 2:

        print(
            "Usage: "
            "python monitoring/kubernetes_feedback.py <job-name>"
        )

        raise SystemExit(1)

    job_name = sys.argv[1]

    print("=" * 60)
    print("KUBERNETES EXECUTION MONITOR")
    print("=" * 60)

    result = wait_for_job(job_name)

    print()
    print(f"Job             : {result['job_name']}")
    print(f"Status          : {result['status']}")
    print(
        f"Runtime         : "
        f"{result['runtime_seconds']:.2f} seconds"
        if result["runtime_seconds"] is not None
        else "Runtime         : unavailable"
    )

    print(f"Started         : {result['started_at']}")
    print(f"Finished        : {result['finished_at']}")

    print("=" * 60)
