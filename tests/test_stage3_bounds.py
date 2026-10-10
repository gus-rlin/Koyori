import threading
import time
from datetime import UTC, datetime

import pytest
from stage3_helpers import goals, submit, task

from koyori.scheduling import Wakes
from koyori.stage3_contracts import RoutineWrite


@pytest.mark.parametrize("parallel", [1, 2])
def test_finite_read_pass_respects_parallel_limit_and_retains_remaining_work(harness, parallel):
    h = harness
    service = goals(h)

    class ReadPlan:
        mode = "simulated"

        def generate(self, payload, quota, repair=None):
            quota.reserve()
            return {
                "summary": "Read context",
                "maxParallelReads": parallel,
                "steps": [
                    {"stepId": f"read{i}", "capability": "memory.context", "arguments": {}}
                    for i in range(3)
                ],
            }

    service.planning = ReadPlan()
    tid = submit(h, "Consulte mes préférences")
    service.sweep()
    original = service._read
    lock = threading.Lock()
    concurrent, peak, calls = 0, 0, 0

    def read(*args):
        nonlocal concurrent, peak, calls
        with lock:
            concurrent += 1
            calls += 1
            peak = max(peak, concurrent)
        try:
            time.sleep(0.05)
            return original(*args)
        finally:
            with lock:
                concurrent -= 1

    service._read = read
    service.sweep()
    assert calls == parallel and peak == parallel
    assert (
        sum(s["status"] == "PENDING" for s in task(h, tid)["stepStates"].values()) == 3 - parallel
    )
    for _ in range(4):
        service.sweep()
    assert task(h, tid)["status"] == "SUCCEEDED" and calls == 3
    assert task(h, tid)["modelCalls"] == 1


def test_cancelled_routine_history_does_not_exhaust_admission_quota(harness):
    h = harness
    h.clock.value = int(datetime(2026, 10, 7, 6, tzinfo=UTC).timestamp())
    service = Wakes(h.domain)
    body = RoutineWrite(
        text="Consulte ma journée", localTime="10:00", startsOn="2026-10-07", endsOn="2026-10-09"
    ).model_dump()
    for _ in range(33):
        ctx = h.domain.context("alex", h.h)
        saved, writes, _ = service.create_rule(ctx, body)
        h.domain.store.transact(ctx.guards() + writes)
        ctx = h.domain.context("alex", h.h)
        _, writes, _ = service.change_rule(ctx, saved["id"], {}, saved["rev"], "cancel")
        h.domain.store.transact(ctx.guards() + writes)
    assert h.domain.context("alex", h.h).household["activeRoutines"] == 0


def test_private_learning_activity_contains_only_minimal_envelopes(harness):
    h = harness
    secret_fixture = "Synthetic confidential preference"
    response = h.client.post(
        "/v1/learning",
        json={
            "kind": "preference",
            "key": "dinner",
            "text": secret_fixture,
            "source": {"kind": "declaration"},
        },
        headers=h.headers(),
    )
    assert response.status_code == 201
    events = [
        e["envelope"]
        for e in h.engine.pending("OUTBOX")
        if e["envelope"]["type"] == "koyori.learning.changed.v1"
    ]
    for event in events:
        h.engine.project_activity(event)
    own = h.client.get("/v1/activity", headers=h.headers()).json()["items"]
    other = h.client.get("/v1/activity", headers=h.headers("sam")).json()["items"]
    assert len(own) == 1 and other == []
    assert secret_fixture not in str(own) and secret_fixture not in str(events)


def test_revoked_routine_owner_releases_quota_without_creating_an_occurrence(harness):
    h = harness
    h.clock.value = int(datetime(2026, 10, 7, 6, tzinfo=UTC).timestamp())
    service = Wakes(h.domain)
    body = RoutineWrite(
        text="Consulte ma journée", localTime="10:00", startsOn="2026-10-07", endsOn="2026-10-09"
    ).model_dump()
    ctx = h.domain.context("sam", h.h)
    saved, writes, _ = service.create_rule(ctx, body)
    h.domain.store.transact(ctx.guards() + writes)
    rule = service.get_rule(ctx, saved["id"])
    wake = h.domain.store.get("Delivery", (f"WAKE#{rule['wakeId']}", "META"))
    assert (
        h.client.delete(
            f"/v1/households/{h.h}/members/sam", headers=h.headers(version=ctx.member["rev"])
        ).status_code
        == 200
    )
    h.clock.value = wake["fireAt"]
    service.deliver(wake["id"])
    assert h.domain.context("alex", h.h).household["activeRoutines"] == 0
    assert h.domain.store.get("Domain", (rule["PK"], rule["SK"]))["active"] is False
