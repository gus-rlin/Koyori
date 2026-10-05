import pytest

from koyori.domain import hkey
from koyori.store import put, revised
from koyori.workers.engine import Publisher


def test_worker_restart_retains_checkpoint_and_fences_old_owner(harness):
    h = harness
    tid = h.command()
    old = h.start(tid)
    checkpoint = h.engine.advance(old)
    assert checkpoint["checkpoint"] == 1
    h.clock.advance(h.settings.lease_seconds + 1)
    resumed = h.engine.acquire(h.h, tid)
    assert resumed["checkpoint"] == 1 and resumed["runEpoch"] > old["runEpoch"]
    assert h.engine.advance(checkpoint) is None
    while resumed and resumed["status"] == "RUNNING":
        resumed = h.engine.advance(resumed)
    result = h.task(tid)
    assert result["status"] == "SUCCEEDED"
    assert result["result"] == {
        "kind": "synthetic",
        "code": "CHECKPOINT_CONFIRMED",
        "markers": ["checkpoint-1", "checkpoint-2"],
    }
    assert h.domain.context("alex", h.h).household["activeTasks"] == 0


def test_duplicate_wake_is_committed_with_inbox(harness):
    h = harness
    tid = h.command()
    event = next(
        x["envelope"] for x in h.engine.pending("OUTBOX") if x["envelope"]["aggregateId"] == tid
    )
    h.engine.consume(event)
    first = h.task(tid)
    h.engine.consume(event)
    assert h.task(tid) == first and first["wakeSeq"] == 1


def test_wake_arriving_during_run_creates_follow_up_intent(harness):
    h = harness
    tid = h.command()
    snapshot = h.start(tid)
    ctx = h.domain.context("alex", h.h)
    wake = h.domain.event(ctx, tid, snapshot["rev"], wake=True)
    h.domain.store.transact([wake])
    h.engine.consume(wake.item["envelope"])
    for _ in range(3):
        snapshot = h.engine.advance(snapshot)
    assert snapshot["status"] == "READY"
    assert snapshot["wakeSeq"] > snapshot["handledWake"]
    assert h.domain.store.get("Delivery", h.engine.run_key(tid))["status"] == "PENDING"
    h.engine.repair()
    assert h.task(tid)["status"] == "SUCCEEDED"


def test_pause_and_cancel_fence_worker_writes(harness):
    h = harness
    tid = h.command()
    snapshot = h.start(tid)
    response = h.client.post(f"/v1/tasks/{tid}/pause", headers=h.headers(version=snapshot["rev"]))
    assert response.status_code == 202
    assert h.engine.advance(snapshot) is None
    intent = h.domain.store.get("Delivery", h.engine.run_key(tid))
    assert intent["status"] == "PENDING" and intent["dueAt"] > h.clock()
    paused = h.task(tid)
    assert (
        h.client.post(
            f"/v1/tasks/{tid}/resume", headers=h.headers(version=paused["rev"])
        ).status_code
        == 202
    )
    fresh = h.start(tid)
    assert (
        h.client.post(
            f"/v1/tasks/{tid}/cancel", headers=h.headers(version=fresh["rev"])
        ).status_code
        == 202
    )
    assert h.engine.advance(fresh) is None
    intent = h.domain.store.get("Delivery", h.engine.run_key(tid))
    assert intent["status"] == "DONE" and "GSI1PK" not in intent
    assert h.domain.context("alex", h.h).household["activeTasks"] == 0


def test_revocation_and_policy_change_stop_current_execution(harness):
    h = harness
    tid = h.command("sam")
    snapshot = h.start(tid)
    assert (
        h.client.delete(
            f"/v1/households/{h.h}/members/sam", headers=h.headers(version=1)
        ).status_code
        == 200
    )
    result = h.engine.advance(snapshot)
    assert result["status"] == "FAILED" and result["checkpoint"] == 0
    assert result["result"]["code"] == "AUTHORITY_REVOKED"
    another = h.command()
    snapshot = h.start(another)
    assert (
        h.client.put(
            "/v1/policies/synthetic", json={"enabled": False}, headers=h.headers(version=1)
        ).status_code
        == 200
    )
    assert h.engine.advance(snapshot)["status"] == "FAILED"


@pytest.mark.parametrize("loss", ["revocation", "expiry", "reenrollment"])
def test_paused_tasks_release_quota_after_owner_loses_authority(harness, loss):
    from koyori.contracts import MemberCreate

    h = harness
    tid = h.command("sam")
    path = f"/v1/households/{h.h}/members/sam"
    assert (
        h.client.patch(
            path,
            json={"expiresAt": h.clock() + 2 * h.settings.lease_seconds},
            headers=h.headers(version=1),
        ).status_code
        == 200
    )
    assert (
        h.client.post(f"/v1/tasks/{tid}/pause", headers=h.headers("sam", version=1)).status_code
        == 202
    )
    paused = h.task(tid, "sam")
    h.clock.advance(h.settings.lease_seconds)
    h.engine.repair()
    assert h.task(tid, "sam") == paused
    assert h.domain.context("alex", h.h).household["activeTasks"] == 1
    if loss != "expiry":
        assert h.client.delete(path, headers=h.headers(version=2)).status_code == 200
        if loss == "reenrollment":
            ctx = h.domain.context("alex", h.h)
            _, writes, _ = h.domain.add_member(ctx, MemberCreate(principalId="sam").model_dump())
            h.domain.store.transact(ctx.guards() + writes)
    else:
        assert h.client.get(f"/v1/tasks/{tid}", headers=h.headers("alex")).status_code == 404
    h.clock.advance(h.settings.lease_seconds)
    h.engine.repair()
    task = h.domain.store.get("Domain", (hkey(h.h), f"TASK#{tid}"))
    assert task["status"] == "FAILED" and task["result"]["code"] == "AUTHORITY_REVOKED"
    assert task["checkpoint"] == paused["checkpoint"] == 0
    assert h.domain.context("alex", h.h).household["activeTasks"] == 0
    assert h.domain.store.get("Delivery", h.engine.run_key(tid))["status"] == "DONE"
    assert h.engine.repair() == 0
    h.command()


def test_publish_crash_and_repair_only_duplicate_delivery(harness):
    h = harness
    tid = h.command()
    event = next(x for x in h.engine.pending("OUTBOX") if x["envelope"]["aggregateId"] == tid)
    sent = []
    publisher = Publisher(h.engine)
    publisher.send = lambda envelope: sent.append(envelope)
    with pytest.raises(RuntimeError, match="Injected crash"):
        publisher.publish_one(event, fail_after_send=True)
    assert h.domain.store.get("Delivery", (event["PK"], event["SK"]))["status"] == "PENDING"
    publisher.publish_one(event)
    assert len(sent) == 2 and sent[0] == sent[1]
    for envelope in sent:
        h.engine.consume(envelope)
    h.engine.repair()
    assert h.task(tid)["status"] == "SUCCEEDED"
    assert h.task(tid)["wakeSeq"] == 1


def test_lost_first_message_recovers_without_consumption(harness):
    h = harness
    tid = h.command()
    event = next(x for x in h.engine.pending("OUTBOX") if x["envelope"]["aggregateId"] == tid)
    queue = []
    publisher = Publisher(h.engine)
    publisher.send = queue.append
    publisher.publish_one(event)
    assert queue and h.domain.store.get("Delivery", (event["PK"], event["SK"]))["status"] == "SENT"
    queue.clear()
    assert h.task(tid)["wakeSeq"] == 0
    assert h.engine.repair() == 1
    assert h.task(tid)["status"] == "SUCCEEDED"
    assert h.task(tid)["wakeSeq"] == 0
    assert h.engine.repair() == 0
    assert h.domain.context("alex", h.h).household["activeTasks"] == 0


@pytest.mark.parametrize("transition", ["resume", "amend"])
def test_ready_transition_recovers_when_its_message_is_lost(harness, transition):
    h = harness
    tid = h.command()
    snapshot = h.start(tid)
    checkpoint = h.engine.advance(snapshot)
    if transition == "resume":
        paused = h.client.post(
            f"/v1/tasks/{tid}/pause", headers=h.headers(version=checkpoint["rev"])
        ).json()
        response = h.client.post(
            f"/v1/tasks/{tid}/resume", headers=h.headers(version=paused["rev"])
        )
    else:
        response = h.client.patch(
            f"/v1/tasks/{tid}",
            json={"label": "Amended"},
            headers=h.headers(version=checkpoint["rev"]),
        )
    assert response.status_code == 202
    assert h.engine.advance(checkpoint) is None
    # No outbox or queue delivery is performed after the control transition.
    assert h.engine.repair() == 1
    assert h.task(tid)["status"] == "SUCCEEDED" and h.task(tid)["checkpoint"] == 2


@pytest.mark.parametrize("legacy_gap", [False, True])
def test_old_event_reconciles_canonical_readiness_without_replaying_wake(harness, legacy_gap):
    h = harness
    tid = h.command()
    event = next(
        x["envelope"] for x in h.engine.pending("OUTBOX") if x["envelope"]["aggregateId"] == tid
    )
    with pytest.raises(ValueError):
        h.engine.consume({**event, "schemaVersion": "2.0"})
    if legacy_gap:
        # Reproduce an accepted record from the original implementation, without its RUN.
        h.domain.store.rows.pop(("Delivery", h.engine.run_key(tid)))
    h.clock.advance(15 * 86400)
    before = h.domain.store.get("Domain", (hkey(h.h), f"TASK#{tid}"))
    h.engine.consume(event)
    assert h.domain.store.get("Domain", (hkey(h.h), f"TASK#{tid}")) == before
    assert h.domain.store.get("Delivery", h.engine.run_key(tid))["status"] == "PENDING"
    inbox = h.domain.store.get("Delivery", (f"INBOX#workflow#{event['eventId']}", "META"))
    assert inbox["outcome"] == "CANONICAL_RECONCILED"
    h.engine.repair()
    assert h.domain.store.get("Domain", (hkey(h.h), f"TASK#{tid}"))["status"] == "SUCCEEDED"


@pytest.mark.parametrize("action", ["pause", "cancel"])
def test_old_event_never_reopens_paused_or_terminal_task(harness, action):
    h = harness
    tid = h.command()
    event = next(
        x["envelope"] for x in h.engine.pending("OUTBOX") if x["envelope"]["aggregateId"] == tid
    )
    assert (
        h.client.post(f"/v1/tasks/{tid}/{action}", headers=h.headers(version=1)).status_code == 202
    )
    before = h.task(tid)
    h.clock.advance(15 * 86400)
    h.engine.consume(event)
    assert h.engine.repair() == int(action == "pause")
    current = h.domain.store.get("Domain", (hkey(h.h), f"TASK#{tid}"))
    assert current["rev"] == before["rev"] and current["status"] == before["status"]


def test_old_event_recovery_rechecks_current_authority(harness):
    h = harness
    tid = h.command("sam")
    event = next(
        x["envelope"] for x in h.engine.pending("OUTBOX") if x["envelope"]["aggregateId"] == tid
    )
    assert (
        h.client.delete(
            f"/v1/households/{h.h}/members/sam", headers=h.headers(version=1)
        ).status_code
        == 200
    )
    h.clock.advance(15 * 86400)
    h.engine.consume(event)
    h.engine.repair()
    task = h.domain.store.get("Domain", (hkey(h.h), f"TASK#{tid}"))
    assert task["status"] == "FAILED" and task["result"]["code"] == "AUTHORITY_REVOKED"
    assert task["checkpoint"] == 0


def test_old_event_respects_a_current_lease(harness):
    h = harness
    tid = h.command()
    event = next(
        x["envelope"] for x in h.engine.pending("OUTBOX") if x["envelope"]["aggregateId"] == tid
    )
    h.clock.advance(15 * 86400)
    leased = h.engine.acquire(h.h, tid)
    intent = h.domain.store.get("Delivery", h.engine.run_key(tid))
    h.engine.consume(event)
    assert h.domain.store.get("Domain", (hkey(h.h), f"TASK#{tid}")) == leased
    assert h.domain.store.get("Delivery", h.engine.run_key(tid)) == intent
    assert h.engine.acquire(h.h, tid) is None
    assert h.engine.advance(leased)["checkpoint"] == 1


def test_activity_duplicates_and_revocation_filter_canonical_permissions(harness):
    h = harness
    tid = h.command(visibility="household")
    event = next(
        x["envelope"] for x in h.engine.pending("OUTBOX") if x["envelope"]["aggregateId"] == tid
    )
    h.engine.project_activity(event)
    h.engine.project_activity(event)
    listed = h.client.get("/v1/activity", headers=h.headers("sam")).json()["items"]
    assert len(listed) == 1 and listed[0]["aggregateId"] == tid
    assert "label" not in listed[0]
    assert (
        h.client.patch(
            f"/v1/tasks/{tid}", json={"visibility": "private"}, headers=h.headers(version=1)
        ).status_code
        == 202
    )
    assert h.client.get("/v1/activity", headers=h.headers("sam")).json()["items"] == []


def test_expiry_is_enforced_even_when_records_are_present(harness):
    h = harness
    tid = h.command("sam")
    member = h.domain.store.get("Domain", (hkey(h.h), "MEMBER#sam"))
    h.domain.store.transact([put("Domain", revised(member, expiresAt=h.clock() + 10), member)])
    h.clock.advance(11)
    h.engine.consume(
        next(
            x["envelope"] for x in h.engine.pending("OUTBOX") if x["envelope"]["aggregateId"] == tid
        )
    )
    assert h.engine.acquire(h.h, tid) is None
    task = h.domain.store.get("Domain", (hkey(h.h), f"TASK#{tid}"))
    assert task["status"] == "FAILED"


def test_a_repeated_checkpoint_snapshot_cannot_advance_twice(harness):
    tid = harness.command()
    snapshot = harness.start(tid)
    assert harness.engine.advance(snapshot)["checkpoint"] == 1
    assert harness.engine.advance(snapshot) is None
    assert harness.task(tid)["checkpoint"] == 1


def test_busy_future_shard_does_not_starve_ready_work_elsewhere(harness):
    from koyori.domain import row

    h = harness
    tid = h.command()
    snapshot = h.start(tid)
    h.engine.advance(snapshot, release=True)
    intent = h.domain.store.get("Delivery", h.engine.run_key(tid))
    h.domain.store.transact([put("Delivery", revised(intent, GSI1PK="RUN#1"), intent)])
    for i in range(105):
        record = row(
            f"RUN#future{i}",
            status="PENDING",
            taskId=f"future{i}",
            h=h.h,
            dueAt=h.clock() + 600,
            GSI1PK="RUN#0",
            GSI1SK=f"{h.clock() + 600:020d}#{i:04d}",
        )
        h.domain.store.transact([put("Delivery", record)])
    h.engine.repair()
    assert h.task(tid)["status"] == "SUCCEEDED"


def test_current_members_receive_activity_after_long_revocation_history(harness):
    from koyori.domain import row

    h = harness
    for i in range(60):
        member = row(
            hkey(h.h),
            f"MEMBER#a-historical-{i:03d}",
            principalId=f"a-historical-{i:03d}",
            role="member",
            kind="personal",
            active=False,
            expiresAt=None,
        )
        h.domain.store.transact([put("Domain", member)])
    tid = h.command(visibility="household")
    event = next(
        x["envelope"] for x in h.engine.pending("OUTBOX") if x["envelope"]["aggregateId"] == tid
    )
    h.engine.project_activity(event)
    assert any(
        e["aggregateId"] == tid
        for e in h.client.get("/v1/activity", headers=h.headers("sam")).json()["items"]
    )
    first = h.client.get(f"/v1/households/{h.h}/members", headers=h.headers()).json()
    assert first["nextCursor"] and len(first["items"]) == 50
    second = h.client.get(
        f"/v1/households/{h.h}/members", params={"cursor": first["nextCursor"]}, headers=h.headers()
    ).json()
    assert any(m["principalId"] == "sam" for m in second["items"])


def test_activity_end_cursor_catches_only_new_durable_entries(harness):
    h = harness
    first = h.command()
    event = next(
        x["envelope"] for x in h.engine.pending("OUTBOX") if x["envelope"]["aggregateId"] == first
    )
    h.engine.project_activity(event)
    page = h.client.get("/v1/activity", headers=h.headers()).json()
    assert page["nextCursor"] is None and page["resumeCursor"]
    second = h.command()
    event = next(
        x["envelope"] for x in h.engine.pending("OUTBOX") if x["envelope"]["aggregateId"] == second
    )
    h.engine.project_activity(event)
    caught = h.client.get(
        "/v1/activity", params={"cursor": page["resumeCursor"]}, headers=h.headers()
    ).json()
    assert [e["aggregateId"] for e in caught["items"]] == [second]
