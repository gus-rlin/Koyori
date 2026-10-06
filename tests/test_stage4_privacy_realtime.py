"""Owned export, fresh erasure, resumable batches and authorized feed catch-up."""

from uuid import uuid4

import pytest

from koyori.domain import hkey
from koyori.errors import Conflict, Problem
from koyori.memory import Memory
from koyori.privacy import Privacy
from koyori.realtime import Signals
from koyori.stage2_contracts import MemoryWrite
from koyori.store import put, revised


def remember(h, actor="alex", text="Synthetic private exchange"):
    ctx = h.domain.context(actor, h.h)
    service = Memory(h.domain)
    body = MemoryWrite(kind="exchange", text=text).model_dump()
    saved = service.mutate(
        ctx, "TEST MEMORY", body, uuid4().hex, None, None, lambda fresh: service.create(fresh, body)
    )
    return saved["id"]


def erase(h):
    body = {"schemaVersion": "1.0", "confirmation": "erase-my-memories"}
    grant = h.grant("POST /v1/privacy/memories/erase", body)
    response = h.client.post(
        "/v1/privacy/memories/erase", json=body, headers=h.headers(grant=grant)
    )
    assert response.status_code == 202, response.text
    return response.json()["id"]


def test_erasure_fresh_auth_batches_survive_and_exclude_other_member(harness):
    h = harness
    own = [remember(h) for _ in range(12)]
    other = remember(h, "sam", "Other member private")
    body = {"confirmation": "erase-my-memories"}
    assert (
        h.client.post("/v1/privacy/memories/erase", json=body, headers=h.headers()).status_code
        == 403
    )
    identifier = erase(h)
    with pytest.raises(Problem, match="MEMORY_ERASING"):
        remember(h)
    Privacy(h.domain).sweep()
    assert Privacy(h.domain).get(h.domain.context("alex", h.h), identifier)["status"] == "RUNNING"
    Privacy(h.domain).sweep()
    for _ in range(6):
        if (
            Privacy(h.domain).get(h.domain.context("alex", h.h), identifier)["status"]
            == "COMPLETED"
        ):
            break
        Privacy(h.domain).sweep()
    final = Privacy(h.domain).get(h.domain.context("alex", h.h), identifier)
    assert final["status"] == "COMPLETED" and final["erased"] == 12
    for mid in own:
        assert h.domain.store.get("Domain", (hkey(h.h), f"MEMORY#{mid}"))["text"] == ""
    assert (
        Memory(h.domain).get(h.domain.context("sam", h.h), other)["text"] == "Other member private"
    )


def test_erasure_fence_defeats_prepared_memory_write(harness):
    h = harness
    ctx = h.domain.context("alex", h.h)
    saved, changes, _ = Memory(h.domain).create(
        ctx, MemoryWrite(kind="exchange", text="Not admitted").model_dump()
    )
    erase(h)
    with pytest.raises(Conflict):
        h.domain.store.transact(ctx.guards() + changes)
    assert h.domain.store.get("Domain", (hkey(h.h), f"MEMORY#{saved['id']}")) is None


@pytest.mark.parametrize("existing_fence", [False, True])
def test_shared_disclosure_loses_to_owner_erasure_before_first_sweep(harness, existing_fence):
    from koyori.channel_tools import ChannelTools
    from koyori.domain import row

    h = harness
    owner, reader = h.domain.context("sam", h.h), h.domain.context("alex", h.h)
    memory = Memory(h.domain)
    saved, changes, _ = memory.create(
        owner,
        MemoryWrite(
            kind="exchange", text="Withdrawn shared memory", visibility="household"
        ).model_dump(),
    )
    h.domain.store.transact(owner.guards() + changes)
    if existing_fence:
        h.domain.store.transact(
            [put("Domain", row(hkey(h.h), "PRIVACY#sam", owner="sam", status="COMPLETE", epoch=1))]
        )
    item = memory.get(reader, saved["id"])
    checks = ChannelTools(h.domain).result_checks(reader, {"items": [item]})
    _, erasing, _ = Privacy(h.domain).start(owner)
    h.domain.store.transact(owner.guards() + erasing)
    with pytest.raises(Conflict):
        h.domain.store.transact(reader.guards() + checks)
    with pytest.raises(Problem):
        memory.read(reader, saved["id"])


def test_export_loses_to_erasure_started_after_memory_was_selected(harness, monkeypatch):
    h = harness
    remember(h)
    ctx = h.domain.context("alex", h.h)
    original = h.domain.store.transact
    armed = True

    def concurrent_start(changes):
        nonlocal armed
        if armed:
            armed = False
            _, erasing, _ = Privacy(h.domain).start(ctx)
            original(ctx.guards() + erasing)
        return original(changes)

    monkeypatch.setattr(h.domain.store, "transact", concurrent_start)
    with pytest.raises(Conflict):
        Privacy(h.domain).export(ctx)


def test_erasure_permanently_invalidates_old_voice_and_channel_grants(harness):
    from test_stage4_sessions import admission

    from koyori.sessions import Sessions

    h = harness
    sessions, admission_result = admission(h)
    sid = admission_result["runtimeSessionId"]
    sessions.consume(admission_result["ticket"], sid)
    secret = Sessions(h.domain).grant(h.domain.context("alex", h.h))
    erase(h)
    Privacy(h.domain).sweep()
    with pytest.raises(Problem):
        sessions.check(sid)
    with pytest.raises(Problem):
        sessions.resolve(secret, "get_daily_context")


def test_export_is_paginated_owned_and_cursors_not_portable(harness):
    h = harness
    remember(h)
    remember(h, "sam", "Forbidden content")
    response = h.client.get("/v1/privacy/export", headers=h.headers())
    assert response.status_code == 200
    assert "Forbidden content" not in response.text
    assert "Synthetic private exchange" in response.text
    assert h.client.get("/v1/privacy/export", headers=h.headers("speaker")).status_code == 403


def test_realtime_token_denies_cross_channel_publish_and_revocation(harness):
    h = harness
    signals = Signals(h.domain)
    admission = signals.subscribe(h.domain.context("alex", h.h))
    event = {
        "authorizationToken": admission["authorizationToken"],
        "requestContext": {
            "operation": "EVENT_SUBSCRIBE",
            "channel": admission["channel"],
        },
    }
    assert signals.authorize(event)["isAuthorized"] is True
    event["requestContext"]["channel"] = f"/activity/{h.h}/sam"
    assert signals.authorize(event)["isAuthorized"] is False
    event["requestContext"]["operation"] = "EVENT_PUBLISH"
    assert signals.authorize(event)["isAuthorized"] is False
    event["requestContext"] = {"operation": "EVENT_CONNECT"}
    member = h.domain.store.get("Domain", (hkey(h.h), "MEMBER#alex"))
    h.domain.store.transact([put("Domain", revised(member, accessEpoch=2), member)])
    assert signals.authorize(event)["isAuthorized"] is False


def test_durable_catchup_after_signal_loss_and_current_visibility(harness):
    h = harness
    tid = h.command()
    outbox = h.engine.pending("OUTBOX")
    for item in outbox:
        h.engine.project_activity(item["envelope"])
    signals = Signals(h.domain)
    feed = signals.catchup(h.domain.context("alex", h.h))
    assert any(item["aggregateId"] == tid for item in feed["items"])
    assert signals.catchup(h.domain.context("sam", h.h))["items"] == []
    signals.sweep()
    assert signals.catchup(h.domain.context("alex", h.h))["items"] == feed["items"]
    assert signals.catchup(h.domain.context("alex", h.h), feed["nextAfter"])["items"] == []
