"""Canonical coordination against DynamoDB Local transactions; external models are simulated."""

from datetime import UTC, datetime

import pytest
from stage2_helpers import commerce
from stage3_helpers import control, goals, progress, submit, task
from test_stage3_recovery import ready_action

from koyori.actions import Actions
from koyori.domain import hkey
from koyori.goals import Goals
from koyori.planner import SimulatedPlanner
from koyori.scheduling import Wakes
from koyori.stage3_contracts import RoutineWrite

pytestmark = pytest.mark.integration
pytest_plugins = ["test_integration"]


def test_dynamo_goal_restart_amend_receipt_and_cancel(dynamo):
    h = dynamo
    commerce(h)
    service = goals(h)
    tid = submit(h)
    original = progress(h, tid, service)
    assert original["status"] == "SUCCEEDED", original
    response = h.client.patch(
        f"/v1/goals/{tid}",
        json={"text": "Prépare le dîner pour quatre demain à 20 h"},
        headers=h.headers(version=original["rev"]),
    )
    assert response.status_code == 200, response.text
    restarted = Goals(h.domain, planning=SimulatedPlanner())
    amended = progress(h, tid, restarted)
    assert amended["status"] == "SUCCEEDED", amended
    assert len(amended["intents"]["dinner"]["actions"]) == 2
    control(h, tid, "cancel")
    assert progress(h, tid, restarted)["status"] == "CANCELLED"
    assert Actions(h.domain).budget(h.domain.context("alex", h.h))["spentMinor"] == 0


def test_dynamo_pause_race_rolls_back_action_claim(dynamo):
    h = dynamo
    commerce(h)
    service = goals(h)
    tid = submit(h)
    aid = ready_action(h, service, tid)
    original = h.domain.store.transact
    raced = False

    def transact(changes):
        nonlocal raced
        if not raced and any(
            c.item and c.item.get("id") == aid and c.item.get("status") == "DISPATCHING"
            for c in changes
        ):
            raced = True
            ctx = h.domain.context("alex", h.h)
            current = task(h, tid)
            _, pause_writes, _ = service.change(ctx, tid, {}, current["rev"], "pause")
            original(ctx.guards() + pause_writes)
        original(changes)

    h.domain.store.transact = transact
    Actions(h.domain).run(h.h, aid)
    h.domain.store.transact = original
    action = Actions(h.domain).get(h.domain.context("alex", h.h), "ACTION", aid)
    assert raced and action["status"] == "BLOCKED"
    assert Actions(h.domain).provider.lookup(action) is None
    assert Actions(h.domain).budget(h.domain.context("alex", h.h))["heldMinor"] == 0


def test_dynamo_occurrence_conflict_and_duplicate_are_atomic(dynamo):
    h = dynamo
    h.clock.value = int(datetime(2026, 10, 6, 6, tzinfo=UTC).timestamp())
    service = Wakes(h.domain)
    ctx = h.domain.context("alex", h.h)
    body = RoutineWrite(
        text="Consulte ma journée", localTime="10:00", startsOn="2026-10-06", endsOn="2026-10-08"
    ).model_dump()
    saved, writes, _ = service.create_rule(ctx, body)
    h.domain.store.transact(ctx.guards() + writes)
    rule = service.get_rule(ctx, saved["id"])
    wake = h.domain.store.get("Delivery", (f"WAKE#{rule['wakeId']}", "META"))
    h.clock.value = wake["fireAt"]
    service.deliver(wake["id"])
    Wakes(h.domain).deliver(wake["id"])
    occurrences, _ = h.domain.store.query("Domain", hkey(h.h), prefix="OCCURRENCE#")
    assert len(occurrences) == 1
    assert h.domain.context("alex", h.h).household["activeTasks"] == 1


def test_dynamo_two_goal_reservations_share_same_budget(dynamo):
    h = dynamo
    commerce(h, limit=3200)
    service = goals(h)
    tids = [submit(h), submit(h)]
    for _ in range(35):
        service.sweep()
        h.clock.advance(5)
    states = [task(h, tid) for tid in tids]
    assert sum(s["status"] == "WAITING_PROVIDER" for s in states) == 1
    assert sum(s.get("error") == "BUDGET_EXCEEDED" for s in states) == 1
    budget = Actions(h.domain).budget(h.domain.context("alex", h.h))
    assert budget["heldMinor"] == 3200 and budget["spentMinor"] == 0
