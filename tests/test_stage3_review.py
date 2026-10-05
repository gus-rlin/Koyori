from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from stage2_helpers import commerce, memory
from stage3_helpers import goals, submit, task

from koyori.actions import Actions
from koyori.contracts import MemberCreate
from koyori.domain import hkey, row
from koyori.scheduling import Wakes
from koyori.security import digest
from koyori.stage3_contracts import RoutineWrite
from koyori.store import put, revised


@pytest.mark.parametrize("phase", ["reservation", "dispatch", "event"])
@pytest.mark.parametrize("change", ["erase", "correct"])
def test_reader_source_outside_prompt_remains_a_live_dependency(harness, phase, change):
    h = harness
    connection = commerce(h)
    recalled = memory(h, key="outside_prompt")
    for _ in range(9):
        h.clock.advance(1)
        memory(h)
    service = goals(h)

    class ReadThenBuy:
        mode = "simulated"

        def generate(self, payload, quota, repair=None):
            quota.reserve()
            assert recalled["id"] not in {m["id"] for m in payload["memories"]}
            return {
                "summary": "Read an older source, then prepare dinner",
                "steps": [
                    {
                        "stepId": "recall",
                        "capability": "memory.context",
                        "arguments": {"key": "outside_prompt"},
                    },
                    {
                        "stepId": "dinner",
                        "capability": "commerce.meals",
                        "dependsOn": ["recall"],
                        "arguments": {
                            "connectionId": connection["id"],
                            "intentKey": "dinner",
                            "lines": [{"sku": "vegetarian-meal", "quantity": 2}],
                            "deliveryAt": h.clock() + 3600,
                        },
                    },
                ],
            }

    service.planning = ReadThenBuy()
    tid = submit(h)
    service.sweep()
    service.sweep()
    assert task(h, tid)["stepStates"]["recall"]["sourceIds"] == [recalled["id"]]
    if phase == "dispatch":
        service.sweep()
        service.sweep()
        assert task(h, tid)["intents"]["dinner"]["actions"]
    if change == "erase":
        response = h.client.delete(
            f"/v1/memories/{recalled['id']}", headers=h.headers(version=recalled["rev"])
        )
    else:
        response = h.client.patch(
            f"/v1/memories/{recalled['id']}",
            json={"text": "Changed context"},
            headers=h.headers(version=recalled["rev"]),
        )
    assert response.status_code == 200
    if phase == "event":
        for record in h.engine.pending("OUTBOX"):
            if record["envelope"]["aggregateId"] == recalled["id"]:
                service.consume(record["envelope"])
        assert task(h, tid)["plan"] is None
    elif phase == "reservation":
        service.sweep()
        assert task(h, tid)["status"] == "NEEDS_ATTENTION"
        assert task(h, tid)["intents"] == {}
    else:
        Actions(h.domain).sweep()
        action_id = task(h, tid)["intents"]["dinner"]["actions"][0]
        action = h.domain.store.get("Domain", (hkey(h.h), f"ACTION#{action_id}"))
        assert action["status"] == "BLOCKED" and action["receipt"] is None


@pytest.mark.parametrize("reason", ["revocation", "expiration"])
def test_paused_routine_releases_quota_without_an_occurrence_wake(harness, reason):
    h = harness
    h.clock.value = int(datetime(2026, 10, 6, 6, tzinfo=UTC).timestamp())
    service = Wakes(h.domain)
    ctx = h.domain.context("sam", h.h)
    body = RoutineWrite(
        text="Consulte ma journée", localTime="10:00", startsOn="2026-10-06", endsOn="2026-10-06"
    ).model_dump()
    saved, writes, _ = service.create_rule(ctx, body)
    h.domain.store.transact(ctx.guards() + writes)
    ctx = h.domain.context("sam", h.h)
    _, writes, _ = service.change_rule(ctx, saved["id"], {}, saved["rev"], "pause")
    h.domain.store.transact(ctx.guards() + writes)
    rule = service.get_rule(ctx, saved["id"])
    assert rule["wakeId"] is None
    if reason == "revocation":
        _, writes, _ = h.domain.change_member(
            h.domain.context("alex", h.h), "sam", {}, ctx.member["rev"], revoke=True
        )
        h.domain.store.transact(h.domain.context("alex", h.h).guards() + writes)
        h.clock.advance(121)
    else:
        h.clock.advance(86400)
    service.sweep()
    assert h.domain.context("alex", h.h).household["activeRoutines"] == 0
    assert h.domain.store.get("Domain", (rule["PK"], rule["SK"]))["active"] is False
    occurrences, _ = h.domain.store.query("Domain", hkey(h.h), prefix="OCCURRENCE#")
    assert occurrences == []
    service.sweep()
    assert h.domain.context("alex", h.h).household["activeRoutines"] == 0


@pytest.mark.parametrize("route", ["routine", "notification-policy"])
def test_unknown_timezone_is_an_input_error(harness, route):
    h = harness
    if route == "routine":
        response = h.client.post(
            "/v1/routines",
            json={
                "text": "Consulte ma journée",
                "localTime": "10:00",
                "startsOn": "2026-10-07",
                "endsOn": "2026-10-09",
                "timeZone": "Atlantis/Nowhere",
            },
            headers=h.headers(),
        )
    else:
        response = h.client.put(
            "/v1/notification-policy",
            json={"timeZone": "Atlantis/Nowhere"},
            headers=h.headers(version=0),
        )
    assert response.status_code == 422


def test_readmission_does_not_keep_an_old_goal_quota_or_authority(harness):
    h = harness
    service = goals(h)
    response = h.client.post(
        "/v1/goals", json={"text": "Consulte ma journée"}, headers=h.headers("sam")
    )
    assert response.status_code == 202
    tid = response.json()["id"]
    ctx = h.domain.context("alex", h.h)
    member = h.domain.context("sam", h.h).member
    _, writes, _ = h.domain.change_member(ctx, "sam", {}, member["rev"], revoke=True)
    h.domain.store.transact(ctx.guards() + writes)
    ctx = h.domain.context("alex", h.h)
    _, writes, _ = h.domain.add_member(ctx, MemberCreate(principalId="sam").model_dump())
    h.domain.store.transact(ctx.guards() + writes)
    assert h.domain.context("sam", h.h).member["accessEpoch"] != task(h, tid)["grantEpoch"]
    service.sweep()
    assert task(h, tid)["status"] == "FAILED"
    assert task(h, tid)["error"] == "ACCESS_REVOKED"
    assert task(h, tid)["modelCalls"] == 0
    assert h.domain.context("alex", h.h).household["activeTasks"] == 0
    service.sweep()
    assert h.domain.context("alex", h.h).household["activeTasks"] == 0


@pytest.mark.parametrize("historical", [101, 501])
def test_account_discovery_pages_past_history_or_reports_its_bound(harness, historical):
    h = harness
    for index in range(historical):
        cid = f"{index:032x}"
        h.domain.store.transact(
            [
                put(
                    "Domain",
                    row(hkey(h.h), f"CONNECTION#{cid}", id=cid, owner="sam", active=False),
                )
            ]
        )
    live_id = "f" * 32
    h.domain.store.transact(
        [
            put(
                "Domain",
                row(
                    hkey(h.h),
                    f"CONNECTION#{live_id}",
                    id=live_id,
                    owner="alex",
                    active=True,
                    provider="commerce-simulator",
                    mode="simulated",
                    capabilities=["commerce.meals"],
                ),
            )
        ]
    )
    service = goals(h)
    tid = submit(h)
    ctx = h.domain.context("alex", h.h)
    payload = service.context_payload(ctx, task(h, tid))
    if historical == 101:
        assert [c["id"] for c in payload["connections"]] == [live_id]
        assert not payload["connectionsTruncated"] and not payload["contextTruncated"]
        service.sweep()
        assert task(h, tid)["status"] == "READY"
    else:
        assert payload["connectionsTruncated"] and payload["contextTruncated"]
        service.sweep()
        assert task(h, tid)["status"] == "NEEDS_ATTENTION"
        assert "incomplète" in task(h, tid)["plan"]["clarification"]


def test_parallel_reads_cannot_silently_exceed_the_durable_source_bound(harness):
    h = harness
    for key in ("older_a", "older_b"):
        for _ in range(8):
            memory(h, key=key)
            h.clock.advance(1)
    for index in range(14):
        memory(h, key=f"recent_{index}")
        h.clock.advance(1)
    service = goals(h)

    class RecallGroups:
        mode = "simulated"

        def generate(self, payload, quota, repair=None):
            quota.reserve()
            assert len(payload["memories"]) == 14
            return {
                "summary": "Read older groups",
                "steps": [
                    {
                        "stepId": key,
                        "capability": "memory.context",
                        "arguments": {"key": key},
                    }
                    for key in ("older_a", "older_b")
                ],
            }

    service.planning = RecallGroups()
    response = h.client.post(
        "/v1/goals",
        json={"text": "Consulte ma journée", "memoryKeys": [f"recent_{i}" for i in range(6)]},
        headers=h.headers(),
    )
    assert response.status_code == 202
    tid = response.json()["id"]
    service.sweep()
    service.sweep()
    current = task(h, tid)
    assert current["status"] == "NEEDS_ATTENTION" and current["error"] == "PLAN_SOURCE_LIMIT"
    assert len(current["planContext"]) == 14 and current["toolCalls"] == 0
    assert all(step["status"] == "PENDING" for step in current["stepStates"].values())


@pytest.mark.parametrize("concurrent", [False, True])
def test_restart_after_last_routine_day_preserves_the_persisted_occurrence(harness, concurrent):
    h = harness
    h.clock.value = int(datetime(2026, 10, 6, 6, tzinfo=UTC).timestamp())
    service = Wakes(h.domain)
    ctx = h.domain.context("alex", h.h)
    body = RoutineWrite(
        text="Consulte ma journée", localTime="10:00", startsOn="2026-10-06", endsOn="2026-10-06"
    ).model_dump()
    saved, writes, _ = service.create_rule(ctx, body)
    h.domain.store.transact(ctx.guards() + writes)
    rule = service.get_rule(ctx, saved["id"])
    wake_id = rule["wakeId"]
    h.clock.advance(86400)
    service = Wakes(h.domain)
    if concurrent:
        candidate = service.pending("RULECHECK")[0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [
                pool.submit(service.check_rule, candidate),
                pool.submit(service.deliver, wake_id),
            ]
            for job in jobs:
                job.result()
    service.sweep()
    service.sweep()
    occurrences, _ = h.domain.store.query("Domain", hkey(h.h), prefix="OCCURRENCE#")
    assert len(occurrences) == 1
    assert h.domain.context("alex", h.h).household["activeRoutines"] == 0
    wake = h.domain.store.get("Delivery", (f"WAKE#{wake_id}", "META"))
    assert wake["outcome"] == "FIRED"
    coordinator = goals(h)
    for _ in range(4):
        coordinator.sweep()
    assert task(h, occurrences[0]["taskId"])["status"] == "SUCCEEDED"


def test_new_simulated_account_after_readmission_uses_current_member_epoch(harness):
    h = harness
    service = goals(h)
    old = h.client.post("/v1/connections/simulated", json={}, headers=h.headers("sam"))
    assert old.status_code == 201
    ctx = h.domain.context("alex", h.h)
    member = h.domain.context("sam", h.h).member
    _, writes, _ = h.domain.change_member(ctx, "sam", {}, member["rev"], revoke=True)
    h.domain.store.transact(ctx.guards() + writes)
    ctx = h.domain.context("alex", h.h)
    _, writes, _ = h.domain.add_member(ctx, MemberCreate(principalId="sam").model_dump())
    h.domain.store.transact(ctx.guards() + writes)
    fresh = h.client.post("/v1/connections/simulated", json={}, headers=h.headers("sam"))
    assert fresh.status_code == 201
    response = h.client.post(
        "/v1/goals",
        json={"text": "Prépare le dîner pour deux demain à 20 h"},
        headers=h.headers("sam"),
    )
    assert response.status_code == 202
    tid = response.json()["id"]
    payload = service.context_payload(h.domain.context("sam", h.h), task(h, tid))
    assert [c["id"] for c in payload["connections"]] == [fresh.json()["id"]]
    assert old.json()["id"] not in {c["id"] for c in payload["connections"]}
    service.sweep()
    assert task(h, tid)["status"] == "READY"


@pytest.mark.parametrize("with_event", [False, True])
def test_declared_third_calendar_is_guarded_even_outside_prompt_snapshots(harness, with_event):
    h = harness
    connection = commerce(h)
    ids = [f"{i:032x}" for i in range(1, 4)]
    for cid in ids:
        h.domain.store.transact(
            [
                put(
                    "Domain",
                    row(
                        hkey(h.h),
                        f"CONNECTION#{cid}",
                        id=cid,
                        owner="alex",
                        active=True,
                        provider="google-calendar",
                        mode="real",
                        capabilities=["calendar.read"],
                        calendarIds=["primary"],
                    ),
                ),
                put("Domain", row(hkey(h.h), f"CALVERSION#{cid}")),
                put(
                    "Domain",
                    row(
                        hkey(h.h),
                        f"CALSYNC#{cid}#{digest({'calendar': 'primary'})}",
                        complete=True,
                    ),
                ),
            ]
        )
    service = goals(h)
    # Explicit snapshot fixture; canonical rights, revisions and synchronization guards remain real.
    service.calendar_snapshot = lambda ctx, run, cid: {
        "evidence": "calendar_snapshot",
        "connectionId": cid,
        "snapshotRevision": 1,
        "items": [],
        "mode": "real",
    }

    class ThirdCalendarPlan:
        mode = "simulated"

        def generate(self, payload, quota, repair=None):
            quota.reserve()
            assert [c["connectionId"] for c in payload["calendarData"]] == ids[:2]
            return {
                "summary": "Prepare dinner with declared calendar dependency",
                "references": [{"kind": "calendar", "id": ids[2], "revision": 1}],
                "steps": [
                    {
                        "stepId": "dinner",
                        "capability": "commerce.meals",
                        "arguments": {
                            "connectionId": connection["id"],
                            "intentKey": "dinner",
                            "lines": [{"sku": "vegetarian-meal", "quantity": 2}],
                            "deliveryAt": h.clock() + 3600,
                        },
                    }
                ],
            }

    service.planning = ThirdCalendarPlan()
    tid = submit(h)
    for _ in range(3):
        service.sweep()
    aid = task(h, tid)["intents"]["dinner"]["actions"][0]
    old = h.domain.store.get("Domain", (hkey(h.h), f"CALVERSION#{ids[2]}"))
    h.domain.store.transact([put("Domain", revised(old), old)])
    if with_event:
        ctx = h.domain.context("alex", h.h)
        event = h.domain.event(ctx, ids[2], 2, kind="calendar", mode="real").item["envelope"]
        service.consume(event)
        assert task(h, tid)["plan"] is None
    Actions(h.domain).sweep()
    action = h.domain.store.get("Domain", (hkey(h.h), f"ACTION#{aid}"))
    assert action["status"] == "BLOCKED" and action["receipt"] is None
