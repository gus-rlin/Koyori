from dataclasses import replace

import pytest
from stage2_helpers import commerce, memory
from stage3_helpers import control, goals, progress, submit, task

from koyori.actions import Actions
from koyori.domain import row
from koyori.errors import Problem
from koyori.goals import Goals
from koyori.planner import CallQuota, SimulatedPlanner
from koyori.store import put, revised


def ready_action(h, service, tid):
    for _ in range(40):
        service.sweep()
        current = task(h, tid)
        if current["intents"].get("dinner", {}).get("actions"):
            return current["intents"]["dinner"]["actions"][-1]
        h.clock.advance(5)
    raise AssertionError(current)


def test_worker_crash_and_stale_run_cannot_overwrite_correction(harness):
    h = harness
    commerce(h)
    service = goals(h)
    tid = submit(h)
    old_run = service.acquire(h.h, tid)
    assert old_run
    h.clock.advance(121)
    fresh = Goals(h.domain, planning=SimulatedPlanner())
    fresh.run(h.h, tid)
    with pytest.raises(Problem, match="RUN_SUPERSEDED"):
        service.current(old_run)
    assert progress(h, tid, fresh)["status"] == "SUCCEEDED"


def test_wake_received_during_run_survives_lease_release(harness):
    h = harness
    service = goals(h)
    tid = submit(h, "Consulte ma journée")
    run = service.acquire(h.h, tid)
    service.wake(h.h, tid, event_id="repeat-event")
    service.wake(h.h, tid, event_id="repeat-event")
    assert task(h, tid)["wakeSeq"] == 1
    ctx = h.domain.context("alex", h.h)
    service._save(run, ctx, dict(status="WAITING_TIME"))
    pending = h.domain.store.get("Delivery", (f"GOALRUN#{tid}", "META"))
    assert pending["status"] == "PENDING" and pending["dueAt"] == h.clock()


def test_pause_resume_reuses_nonexecuted_intent_with_fresh_quote(harness):
    h = harness
    commerce(h)
    service = goals(h)
    tid = submit(h)
    aid = ready_action(h, service, tid)
    original_intent = task(h, tid)["intents"]["dinner"]["intentionId"]
    control(h, tid, "pause")
    Actions(h.domain).run(h.h, aid)
    assert (
        Actions(h.domain).get(h.domain.context("alex", h.h), "ACTION", aid)["status"] == "BLOCKED"
    )
    control(h, tid, "resume")
    done = progress(h, tid, service)
    assert done["status"] == "SUCCEEDED", done
    assert done["intents"]["dinner"]["intentionId"] == original_intent
    assert len(done["intents"]["dinner"]["actions"]) == 2


def test_amend_unknown_operation_reconciles_before_any_new_planning(harness):
    h = harness
    commerce(h)
    h.domain.store.transact(
        [
            put(
                "Domain",
                row(
                    "PROVIDER#commerce-simulator",
                    prices={
                        "milk": 180,
                        "bread": 250,
                        "fruit": 400,
                        "vegetarian-meal": 1400,
                        "chicken-meal": 1600,
                    },
                    fault="timeout-after-commit",
                ),
            )
        ]
    )
    service = goals(h)
    tid = submit(h)
    aid = ready_action(h, service, tid)
    Actions(h.domain).run(h.h, aid)
    assert (
        Actions(h.domain).get(h.domain.context("alex", h.h), "ACTION", aid)["status"] == "UNKNOWN"
    )
    current = task(h, tid)
    old_calls = current["modelCalls"]
    response = h.client.patch(
        f"/v1/goals/{tid}",
        json={"text": "Prépare le dîner pour quatre demain à 20 h"},
        headers=h.headers(version=current["rev"]),
    )
    assert response.status_code == 200
    service.sweep()
    assert task(h, tid)["status"] == "WAITING_PROVIDER"
    assert task(h, tid)["modelCalls"] == old_calls
    h.clock.advance(31)
    done = progress(h, tid, service)
    assert done["status"] == "SUCCEEDED", done
    assert len(done["intents"]["dinner"]["actions"]) == 2


def test_reasoning_budget_does_not_disable_provider_reconciliation(harness):
    h = harness
    h.domain.settings = replace(h.domain.settings, reasoning_task_limit=2)
    commerce(h)
    service = goals(h)
    tid = submit(h)
    aid = ready_action(h, service, tid)
    current = task(h, tid)
    h.domain.store.transact([put("Domain", revised(current, modelCalls=2), current)])
    control(h, tid, "pause")
    Actions(h.domain).run(h.h, aid)
    assert (
        Actions(h.domain).get(h.domain.context("alex", h.h), "ACTION", aid)["status"] == "BLOCKED"
    )
    control(h, tid, "resume")
    service.sweep()
    assert task(h, tid)["error"] == "REASONING_LIMIT"
    assert task(h, tid)["modelCalls"] == 2


def test_late_acceptance_event_does_not_restart_failed_model(harness):
    h = harness

    class Broken:
        mode = "simulated"

        def generate(self, payload, quota, repair=None):
            quota.reserve()
            raise TimeoutError

    service = goals(h)
    service.planning = Broken()
    tid = submit(h)
    event = next(
        e["envelope"] for e in h.engine.pending("OUTBOX") if e["envelope"]["aggregateId"] == tid
    )
    service.sweep()
    assert task(h, tid)["status"] == "NEEDS_ATTENTION"
    service.consume(event)
    service.sweep()
    assert task(h, tid)["modelCalls"] == 1


def test_memory_correction_before_dispatch_blocks_stale_conditions(harness):
    h = harness
    commerce(h)
    source = memory(h)
    service = goals(h)
    tid = submit(h)
    aid = ready_action(h, service, tid)
    response = h.client.patch(
        f"/v1/memories/{source['id']}",
        json={"text": "Different preference"},
        headers=h.headers(version=source["rev"]),
    )
    assert response.status_code == 200
    Actions(h.domain).run(h.h, aid)
    assert (
        Actions(h.domain).get(h.domain.context("alex", h.h), "ACTION", aid)["status"] == "BLOCKED"
    )
    event = next(
        e["envelope"]
        for e in h.engine.pending("OUTBOX")
        if e["envelope"]["aggregateId"] == source["id"] and e["envelope"]["aggregateVersion"] == 2
    )
    service.consume(event)
    assert task(h, tid)["plan"] is None
    done = progress(h, tid, service)
    assert done["status"] == "SUCCEEDED", done


def test_quota_checks_current_owner_and_run_before_each_model_request(harness):
    h = harness
    service = goals(h)
    tid = submit(h)
    run = service.acquire(h.h, tid)
    quota = CallQuota(h.domain, h.h, tid, run["runEpoch"])
    quota.reserve()
    control(h, tid, "pause")
    with pytest.raises(Problem, match="RUN_SUPERSEDED"):
        quota.reserve()
    assert task(h, tid)["modelCalls"] == 1


def test_pause_and_reasoning_exhaustion_do_not_prevent_unknown_receipt_recovery(harness):
    h = harness
    commerce(h)
    h.domain.settings = replace(h.domain.settings, reasoning_task_limit=2)
    h.domain.store.transact(
        [
            put(
                "Domain",
                row(
                    "PROVIDER#commerce-simulator",
                    prices={"chicken-meal": 1600},
                    fault="timeout-after-commit",
                ),
            )
        ]
    )
    service = goals(h)
    tid = submit(h)
    aid = ready_action(h, service, tid)
    Actions(h.domain).run(h.h, aid)
    current = task(h, tid)
    h.domain.store.transact([put("Domain", revised(current, modelCalls=2), current)])
    control(h, tid, "pause")
    h.clock.advance(31)
    Actions(h.domain).run(h.h, aid)
    assert (
        Actions(h.domain).get(h.domain.context("alex", h.h), "ACTION", aid)["status"] == "CONFIRMED"
    )
    assert task(h, tid)["modelCalls"] == 2
    assert task(h, tid)["status"] == "PAUSED"
