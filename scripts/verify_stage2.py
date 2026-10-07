"""Observable local stage-two recipe. Stops project workers and restarts storage/API."""

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from verify_local import BASE, ROOT, compose, demo_household, wait_ready, worker_environment

from koyori.stage2_contracts import BudgetPut, MemoryWrite


def proof(client, operation, body, version=None):
    from koyori.security import request_hash

    response = client.post(
        "/v1/auth/step-up",
        json={"operation": operation, "requestHash": request_hash(body, version)},
        headers={"Idempotency-Key": uuid4().hex},
    )
    assert response.status_code == 201, response.status_code
    challenge = response.json()
    signed = compose(
        "run",
        "--rm",
        "--no-deps",
        "demo",
        "python",
        "-c",
        "import sys; from koyori.config import Settings; from koyori.demo import token; print(token(Settings.from_env(),sys.argv[1],nonce=sys.argv[2]))",
        "alex",
        challenge["nonce"],
    ).strip()
    response = client.post(
        f"/v1/auth/step-up/{challenge['id']}/complete",
        json={"identityProof": signed},
        headers={"Idempotency-Key": uuid4().hex},
    )
    assert response.status_code == 200, response.status_code
    return response.json()["grant"]


def main():
    wait_ready()
    access = compose(
        "run", "--rm", "--no-deps", "demo", "python", "-m", "koyori.demo", "token", "alex"
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

        def write(path, body, method="POST", version=None, grant=None, key=None):
            headers = {"Idempotency-Key": key or uuid4().hex}
            if version is not None:
                headers["If-Match"] = f'"{version}"'
            if grant:
                headers["X-Step-Up-Grant"] = grant
            response = client.request(method, path, json=body, headers=headers)
            assert response.status_code in {200, 201, 202}, (path, response.status_code)
            return response.json()

        zone = ZoneInfo(household["timeZone"])
        yesterday = datetime.now(zone) - timedelta(days=1)
        body = MemoryWrite(
            kind="exchange",
            text="Synthetic request for a sweet breakfast",
            occurredAt=int(yesterday.timestamp()),
        ).model_dump()
        memory = write("/v1/memories", body)
        context = client.post("/v1/context", json={"day": "yesterday"}).json()
        assert memory["id"] in {x["id"] for x in context["items"]}
        write(
            f"/v1/memories/{memory['id']}",
            {"text": "Synthetic correction: less sweet"},
            "PATCH",
            version=1,
        )
        write(f"/v1/memories/{memory['id']}", {}, "DELETE", version=2)
        assert client.get(f"/v1/memories/{memory['id']}").status_code == 404
        connection = write("/v1/connections/simulated", {})
        budget = client.get("/v1/budget").json()
        body = BudgetPut(
            limitMinor=budget.get("spentMinor", 0) + budget.get("heldMinor", 0) + 1000,
            perActionMinor=1000,
            approvalRequired=False,
        ).model_dump()
        write(
            "/v1/budget",
            body,
            "PUT",
            version=budget["rev"],
            grant=proof(client, "PUT /v1/budget", body, budget["rev"]),
        )
        quote = write(
            "/v1/quotes",
            {
                "connectionId": connection["id"],
                "intentionId": uuid4().hex,
                "capability": "commerce.groceries",
                "lines": [{"sku": "milk", "quantity": 1}],
                "deliveryAt": int(time.time()) + 3600,
            },
        )
        key = uuid4().hex
        action = write("/v1/actions", {"quoteId": quote["id"]}, key=key)
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        process = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts/crash_action_worker.py"), h, action["id"]],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=flags,
            env=worker_environment(),
        )
        reader = ThreadPoolExecutor(max_workers=1)
        try:
            line = reader.submit(process.stdout.readline).result(timeout=20)
        finally:
            reader.shutdown(wait=False, cancel_futures=True)
        assert line.strip() == "PROVIDER_COMMITTED" and process.poll() is None
        process.kill()
        process.wait(timeout=10)
        process = None
        current = client.get(f"/v1/actions/{action['id']}").json()
        assert current["status"] == "DISPATCHING" and current["receipt"] is None
        assert client.get("/v1/budget").json()["heldMinor"] >= 180
        compose("stop", "api")
        compose("restart", "dynamodb", "elasticmq")
        compose("start", "api")
        wait_ready()
        replay = write("/v1/actions", {"quoteId": quote["id"]}, key=key)
        assert replay["id"] == action["id"]
        compose("start", *stopped)
        for _ in range(65):
            current = client.get(f"/v1/actions/{action['id']}").json()
            if current["status"] == "CONFIRMED":
                break
            time.sleep(1)
        assert current["status"] == "CONFIRMED" and current["receipt"]["kind"] == "simulated"
        assert current["receipt"]["operationId"] == action["id"]
        report = {
            "schemaVersion": "1.0",
            "scope": "local-emulators-and-simulated-commerce",
            "result": "PASS",
            "checks": {
                "localYesterdayRecall": True,
                "correctionAndErasure": True,
                "providerCommittedBeforeProcessKilled": True,
                "reservationKeptWithoutReceipt": True,
                "storageAndApiRestart": True,
                "idempotentReplaySameAction": True,
                "sameProviderOperationReconciled": True,
            },
            "googleQualified": False,
            "awsQualified": False,
        }
        (ROOT / "artifacts/stage2-recovery.json").write_text(
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
