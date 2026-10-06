"""Observable Docker recovery recipe; synthetic fixture data and no tokens in reports."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = f"http://127.0.0.1:{os.getenv('KOYORI_API_PORT', '8088')}"


def compose(*args):
    return subprocess.run(
        ["docker", "compose", *args], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout


def worker_environment():
    """Host helpers must use the same isolated emulator ports as Compose."""
    environment = dict(os.environ)
    environment["KOYORI_DDB_ENDPOINT"] = f"http://127.0.0.1:{os.getenv('KOYORI_DDB_PORT', '8800')}"
    environment["KOYORI_SQS_ENDPOINT"] = f"http://127.0.0.1:{os.getenv('KOYORI_SQS_PORT', '9324')}"
    return environment


def wait_ready():
    for _ in range(60):
        try:
            if httpx.get(BASE + "/health/ready", timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise RuntimeError("API did not become ready")


def main():
    wait_ready()
    # Capture bearer credentials in memory only; neither commands nor reports print them.
    access = compose(
        "run", "--rm", "--no-deps", "demo", "python", "-m", "koyori.demo", "token", "alex"
    ).strip()
    other = compose(
        "run", "--rm", "--no-deps", "demo", "python", "-m", "koyori.demo", "token", "robin"
    ).strip()
    client = httpx.Client(base_url=BASE, timeout=10, headers={"Authorization": f"Bearer {access}"})
    h = client.get("/v1/households").json()["items"][0]["id"]
    client.headers["X-Household-Id"] = h
    bookmark = None
    for _ in range(100):
        page = client.get("/v1/activity", params={"cursor": bookmark} if bookmark else {}).json()
        bookmark = page.get("resumeCursor")
        if not page["nextCursor"]:
            break
        bookmark = page["nextCursor"]
    else:
        raise RuntimeError("Qualification feed exceeds bounded catch-up")
    stopped = [
        "workflow",
        "repair",
        "publisher",
        "activity",
        "connector",
        "projection",
        "coordinator",
        "scheduler",
        "notifications",
    ]
    compose("stop", *stopped)
    process = None
    try:
        key = uuid4().hex
        body = {"operation": "synthetic.checkpoint", "label": "Docker crash recovery recipe"}
        accepted = client.post("/v1/commands", json=body, headers={"Idempotency-Key": key})
        assert accepted.status_code == 202, accepted.status_code
        tid = accepted.json()["taskId"]
        created = client.get(f"/v1/tasks/{tid}").json()
        assert created["status"] == "READY"
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        process = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts/crash_worker.py"), h, tid],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=flags,
            env=worker_environment(),
        )
        # The bounded worker commits before its readiness line, then stays live.
        from concurrent.futures import ThreadPoolExecutor

        reader = ThreadPoolExecutor(max_workers=1)
        try:
            line = reader.submit(process.stdout.readline).result(timeout=20)
        finally:
            reader.shutdown(wait=False, cancel_futures=True)
        assert line.strip() == "CHECKPOINT_COMMITTED"
        assert process.poll() is None
        process.kill()
        process.wait(timeout=10)
        process = None
        checkpoint = client.get(f"/v1/tasks/{tid}").json()
        assert checkpoint["status"] == "RUNNING" and checkpoint["checkpoint"] == 1
        # Restart storage and API as well as the process that owned the interrupted run.
        compose("stop", "api")
        compose("restart", "dynamodb", "elasticmq")
        compose("start", "api")
        wait_ready()
        resumed = client.get(f"/v1/tasks/{tid}")
        assert resumed.status_code == 200 and resumed.json()["checkpoint"] == 1
        replay = client.post("/v1/commands", json=body, headers={"Idempotency-Key": key})
        assert replay.status_code == 202 and replay.json() == accepted.json()
        outsider = httpx.get(
            BASE + f"/v1/tasks/{tid}",
            headers={"Authorization": f"Bearer {other}", "X-Household-Id": h},
            timeout=5,
        )
        assert outsider.status_code == 403
        compose("start", *stopped)
        finished = None
        for _ in range(65):
            finished = client.get(f"/v1/tasks/{tid}").json()
            if finished["status"] in {"SUCCEEDED", "FAILED"}:
                break
            time.sleep(1)
        assert finished["status"] == "SUCCEEDED", finished["status"]
        assert finished["result"]["kind"] == "synthetic" and finished["checkpoint"] == 2
        found = []
        for _ in range(30):
            page = client.get(
                "/v1/activity", params={"cursor": bookmark} if bookmark else {}
            ).json()
            found = [entry for entry in page["items"] if entry["aggregateId"] == tid]
            if page["nextCursor"]:
                bookmark = page["nextCursor"]
            if found:
                break
            time.sleep(1)
        assert found
        report = {
            "schemaVersion": "1.0",
            "mode": "synthetic-local",
            "checks": {
                "acceptedBeforeInterruption": True,
                "liveWorkerKilledAfterCommittedCheckpoint": True,
                "storageAndApiRestartPreservedTask": True,
                "idempotentReplaySameTask": True,
                "crossHouseholdDenied": True,
                "sameTaskCompletedAfterLeaseRecovery": True,
                "durableActivityObserved": True,
            },
            "result": "PASS",
        }
        path = ROOT / "artifacts/local-recovery.json"
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report))
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        compose("start", "api", *stopped)
        client.close()


if __name__ == "__main__":
    main()
