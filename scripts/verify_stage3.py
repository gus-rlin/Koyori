"""Process interruption and durable stage-three recipe using only synthetic household data."""

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from verify_local import BASE, ROOT, compose, demo_household, wait_ready, worker_environment
from verify_stage2 import proof

from koyori.stage2_contracts import BudgetPut
from koyori.stage3_contracts import LearningSubmit, NotificationPolicy, RoutineWrite


def main():
    wait_ready()
    access = compose(
        "run", "--rm", "--no-deps", "demo", "python", "-m", "koyori.demo", "token", "alex"
    ).strip()
    other = compose(
        "run", "--rm", "--no-deps", "demo", "python", "-m", "koyori.demo", "token", "sam"
    ).strip()
    client = httpx.Client(base_url=BASE, timeout=15, headers={"Authorization": f"Bearer {access}"})
    household = demo_household(client)
    h = household["id"]
    client.headers["X-Household-Id"] = h
    stopped = [
        "connector",
        "projection",
        "workflow",
        "repair",
        "publisher",
        "activity",
        "coordinator",
        "scheduler",
        "notifications",
    ]
    compose("stop", *stopped)
    process = None
    try:

        def write(path, body=None, *, method="POST", version=None, grant=None, key=None):
            headers = {"Idempotency-Key": key or uuid4().hex}
            if version is not None:
                headers["If-Match"] = f'"{version}"'
            if grant:
                headers["X-Step-Up-Grant"] = grant
            response = client.request(method, path, json=body, headers=headers)
            assert response.status_code in {200, 201, 202}, (
                path,
                response.status_code,
                response.json().get("code"),
            )
            return response.json()

        def goal(tid):
            for attempt in range(3):
                try:
                    response = client.get(f"/v1/goals/{tid}")
                    assert response.status_code == 200, response.status_code
                    return response.json()
                except httpx.TransportError:
                    if attempt == 2:
                        raise
                    time.sleep(0.2)

        def wait_goal(tid, status, seconds=130):
            for _ in range(seconds):
                current = goal(tid)
                if current["status"] == status:
                    return current
                assert current["status"] not in {"FAILED", "NEEDS_ATTENTION"}, current.get("error")
                time.sleep(1)
            raise AssertionError(("Goal timed out", current["status"]))

        write("/v1/connections/simulated", {})
        budget = client.get("/v1/budget").json()
        body = BudgetPut(
            limitMinor=budget.get("spentMinor", 0) + budget.get("heldMinor", 0) + 50000,
            perActionMinor=20000,
            approvalRequired=False,
        ).model_dump()
        write(
            "/v1/budget",
            body,
            method="PUT",
            version=budget["rev"],
            grant=proof(client, "PUT /v1/budget", body, budget["rev"]),
        )
        policy = client.get("/v1/notification-policy").json()
        write(
            "/v1/notification-policy",
            NotificationPolicy(groupSeconds=0, quietStart="08:00", quietEnd="08:00").model_dump(),
            method="PUT",
            version=policy.get("rev", 0),
        )
        learning_key = f"recipe_dinner_{uuid4().hex}"
        feedback = write(
            "/v1/learning",
            LearningSubmit(
                text="Je préfère un dîner végétarien",
                kind="preference",
                key=learning_key,
                source={"kind": "declaration"},
            ).model_dump(),
        )
        learned = write(
            f"/v1/learning/{feedback['id']}/decisions",
            {"decision": "accept"},
            version=feedback["rev"],
        )
        assert learned["memoryId"]
        key = uuid4().hex
        body = {"text": "Prépare le dîner pour deux demain à 20 h", "memoryKeys": [learning_key]}
        created = write("/v1/goals", body, key=key)
        tid = created["id"]
        process = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts/crash_goal_worker.py"), h, tid],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=worker_environment(),
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        reader = ThreadPoolExecutor(max_workers=1)
        try:
            line = reader.submit(process.stdout.readline).result(timeout=20)
        finally:
            reader.shutdown(wait=False, cancel_futures=True)
        assert line.strip() == "PLAN_COMMITTED" and process.poll() is None
        process.kill()
        process.wait(timeout=10)
        process = None
        assert goal(tid)["planRevision"] == 1
        compose("stop", "api")
        compose("restart", "dynamodb", "elasticmq")
        compose("start", "api")
        wait_ready()
        assert write("/v1/goals", body, key=key)["id"] == tid
        denied = httpx.get(
            BASE + f"/v1/goals/{tid}",
            headers={"Authorization": f"Bearer {other}", "X-Household-Id": h},
        )
        assert denied.status_code == 404
        # One bounded routine occurrence is scheduled in parallel with the goal wait.
        local = (
            (datetime.now(UTC) + timedelta(minutes=1))
            .replace(second=0, microsecond=0)
            .astimezone(ZoneInfo("Europe/Paris"))
        )
        routine = write(
            "/v1/routines",
            RoutineWrite(
                text="Consulte ma journée",
                timeZone="Europe/Paris",
                localTime=local.strftime("%H:%M"),
                startsOn=local.date().isoformat(),
                endsOn=local.date().isoformat(),
            ).model_dump(),
        )
        compose("start", *stopped)
        wait_goal(tid, "WAITING_TIME", 30)
        time.sleep(2)
        assert goal(tid)["modelCalls"] == 1
        paused = write(f"/v1/goals/{tid}/pause", version=goal(tid)["rev"])
        assert paused["status"] == "PAUSED"
        write(f"/v1/goals/{tid}/resume", version=paused["rev"])
        done = wait_goal(tid, "SUCCEEDED")
        assert done["modelCalls"] == 2 and done["planRevision"] == 2
        first = done["actions"][0]
        assert (
            first["receipt"]["kind"] == "simulated"
            and first["conditions"]["lines"][0]["sku"] == "vegetarian-meal"
        )
        write(
            f"/v1/goals/{tid}",
            {"text": "Finalement nous serons quatre"},
            method="PATCH",
            version=done["rev"],
        )
        amended = wait_goal(tid, "SUCCEEDED", 45)
        latest = amended["actions"][-1]
        assert latest["conditions"]["operation"] == "modify"
        assert latest["businessId"] == first["businessId"]
        assert latest["conditions"]["lines"][0]["quantity"] == 4
        write(f"/v1/goals/{tid}/cancel", version=amended["rev"])
        cancelled = wait_goal(tid, "CANCELLED", 45)
        assert cancelled["actions"][-1]["receipt"]["status"] == "CANCELLED"
        # Reload the durable occurrence, then redeliver its wake twice through the same service.
        import os

        from koyori.domain import hkey
        from koyori.scheduling import Wakes
        from koyori.security import digest
        from koyori.workers.runtime import engine

        os.environ.update(worker_environment())
        domain = engine().domain
        wakes = Wakes(domain)
        canonical_rule = wakes.get_rule(domain.context("alex", h), routine["id"])
        wake_id = routine["wakeId"]
        wakes.deliver(wake_id)
        wakes.deliver(wake_id)
        occurrence_id = digest(
            {"rule": routine["id"], "version": 1, "local": local.strftime("%Y-%m-%dT%H:%M")}
        )[:32]
        matches, _ = domain.store.query(
            "Domain", hkey(h), prefix=f"OCCURRENCE#{occurrence_id}", limit=2
        )
        assert len(matches) == 1 and not canonical_rule["active"]
        wait_goal(matches[0]["taskId"], "SUCCEEDED", 30)
        for _ in range(20):
            notifications, cursor = [], None
            for _ in range(100):
                page = client.get(
                    "/v1/notifications", params={"cursor": cursor} if cursor else {}
                ).json()
                notifications += page["items"]
                cursor = page.get("nextCursor")
                if not cursor:
                    break
            if any(e["id"] == tid for n in notifications for e in n["entries"]):
                break
            time.sleep(1)
        assert any(e["id"] == tid for n in notifications for e in n["entries"])
        report = {
            "schemaVersion": "1.0",
            "scope": "local-emulators-simulated-planner-and-commerce",
            "result": "PASS",
            "checks": {
                "liveProcessKilledAfterCommittedPlan": True,
                "storageAndApiRestartPreservedPlan": True,
                "idempotentGoalReplay": True,
                "ownerIsolation": True,
                "waitWithoutAdditionalModelCall": True,
                "pauseResumeWithFreshPlan": True,
                "acceptedPreferenceUsedInQuote": True,
                "amendSamePurchaseForFour": True,
                "providerCancellationReceiptRequired": True,
                "oneRoutineOccurrenceAfterRepeatedWake": True,
                "groupedNotificationFeed": True,
            },
            "liveNovaQualified": False,
            "awsQualified": False,
        }
        (ROOT / "artifacts/stage3-recovery.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report))
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        compose("start", "api", *stopped)
        client.close()


if __name__ == "__main__":
    main()
