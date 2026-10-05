from datetime import UTC, date, datetime

import pytest
from stage3_helpers import submit, task

from koyori.domain import hkey
from koyori.errors import Problem
from koyori.scheduling import Wakes, civil_timestamp
from koyori.stage3_contracts import RoutineWrite


def routine(h, **overrides):
    body = RoutineWrite(
        text="Prépare le dîner demain à 20 h",
        localTime="10:00",
        startsOn="2026-10-06",
        endsOn="2026-10-09",
        **overrides,
    ).model_dump()
    response = h.client.post("/v1/routines", json=body, headers=h.headers())
    assert response.status_code == 201, response.text
    return response.json()


def test_dst_gap_skip_reject_and_overlap_recorded_policy():
    assert civil_timestamp(date(2027, 3, 28), "02:30", "Europe/Paris") is None
    with pytest.raises(Problem, match="NONEXISTENT_LOCAL_TIME"):
        civil_timestamp(date(2027, 3, 28), "02:30", "Europe/Paris", nonexistent="reject")
    first = civil_timestamp(date(2026, 10, 25), "02:30", "Europe/Paris", ambiguous="first")
    second = civil_timestamp(date(2026, 10, 25), "02:30", "Europe/Paris", ambiguous="second")
    assert second - first == 3600


def test_duplicate_occurrence_after_overlap_creates_one_goal(harness):
    h = harness
    h.clock.value = int(datetime(2026, 10, 24, 20, tzinfo=UTC).timestamp())
    body = RoutineWrite(
        text="Prépare le dîner à 20 h",
        localTime="02:30",
        timeZone="Europe/Paris",
        startsOn="2026-10-25",
        endsOn="2026-10-25",
    ).model_dump()
    service = Wakes(h.domain)
    ctx = h.domain.context("alex", h.h)
    response, writes, _ = service.create_rule(ctx, body)
    h.domain.store.transact(ctx.guards() + writes)
    rule = service.get_rule(ctx, response["id"])
    wake = h.domain.store.get("Delivery", (f"WAKE#{rule['wakeId']}", "META"))
    h.clock.value = wake["fireAt"]
    service.deliver(wake["id"])
    service.deliver(wake["id"])
    h.clock.advance(3600)
    service.deliver(wake["id"])
    occurrences, _ = h.domain.store.query("Domain", hkey(h.h), prefix="OCCURRENCE#")
    assert len(occurrences) == 1
    assert task(h, occurrences[0]["taskId"])["occurrence"]["local"] == "2026-10-25T02:30"


def test_old_rule_wake_after_pause_or_amend_cannot_create_goal(harness):
    h = harness
    h.clock.value = int(datetime(2026, 10, 6, 6, tzinfo=UTC).timestamp())
    service = Wakes(h.domain)
    body = RoutineWrite(
        text="Consulte ma journée", localTime="10:00", startsOn="2026-10-06", endsOn="2026-10-09"
    ).model_dump()
    ctx = h.domain.context("alex", h.h)
    result, writes, _ = service.create_rule(ctx, body)
    h.domain.store.transact(ctx.guards() + writes)
    old_rule = service.get_rule(ctx, result["id"])
    old_wake = h.domain.store.get("Delivery", (f"WAKE#{old_rule['wakeId']}", "META"))
    ctx = h.domain.context("alex", h.h)
    _, writes, _ = service.change_rule(ctx, old_rule["id"], {}, old_rule["rev"], "pause")
    h.domain.store.transact(ctx.guards() + writes)
    h.clock.value = old_wake["fireAt"] + 61
    service.deliver(old_wake["id"])
    occurrences, _ = h.domain.store.query("Domain", hkey(h.h), prefix="OCCURRENCE#")
    assert occurrences == []


def test_missed_wake_is_repaired_and_late_goal_wake_is_stale(harness):
    h = harness
    tid = submit(h)
    current = task(h, tid)
    service = Wakes(h.domain)
    writes = service.goal_wake(current, h.clock() + 60)
    h.domain.store.transact(writes)
    wake = writes[0].item
    service.sweep()
    assert h.domain.store.get("Delivery", (wake["PK"], wake["SK"]))["schedulerState"] == "LOCAL"
    h.clock.advance(61)
    service.sweep()
    assert task(h, tid)["wakeSeq"] == 1
    service.deliver(wake["id"])
    assert task(h, tid)["wakeSeq"] == 1


def test_routine_contract_rejects_unbounded_dates_and_unknown_fields():
    with pytest.raises(ValueError):
        RoutineWrite(text="Dinner", localTime="02:30", startsOn="2026-01-01", endsOn="2028-01-01")
    with pytest.raises(ValueError):
        RoutineWrite(
            text="Dinner",
            localTime="02:30",
            startsOn="2026-01-01",
            endsOn="2026-01-02",
            grant="approve-all",
        )
