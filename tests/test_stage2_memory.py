import json
from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from stage2_helpers import memory

from koyori.domain import hkey, row
from koyori.errors import Conflict
from koyori.memory import Memory
from koyori.semantic import Semantic
from koyori.stage2_contracts import MemoryPatch, MemoryWrite
from koyori.store import put, revised


def test_disabled_semantic_worker_drains_intents_and_preserves_newer_mutations(harness):
    h = harness
    service = Semantic(h.domain)
    service.mode = "disabled"
    items = [memory(h) for _ in range(25)]
    stale = h.domain.store.get("Delivery", (f"MEMINDEX#{items[0]['id']}", "META"))
    assert (
        h.client.patch(
            f"/v1/memories/{items[0]['id']}",
            json={"text": "Correction"},
            headers=h.headers(version=1),
        ).status_code
        == 200
    )
    service.project(stale)
    latest = h.domain.store.get("Delivery", (stale["PK"], stale["SK"]))
    assert latest["status"] == "PENDING" and latest["memoryRev"] == 2
    assert (
        h.client.delete(f"/v1/memories/{items[1]['id']}", headers=h.headers(version=1)).status_code
        == 200
    )
    assert service.sweep() > 0
    service.sweep()
    assert service.sweep() == 0
    assert not service.pending("MEMINDEX") and not service.pending("MEMERASE")
    for item in items:
        intent = h.domain.store.get("Delivery", (f"MEMINDEX#{item['id']}", "META"))
        assert intent["status"] == "DONE" and "GSI1PK" not in intent and "GSI1SK" not in intent
    assert not any(pk.startswith(("VECTOR#", "EMBEDUSE#")) for _, (pk, _) in h.domain.store.rows)


@pytest.mark.parametrize("day", ["9999-12-31", "0001-01-01"])
def test_context_rejects_unrepresentable_day_boundaries(harness, day):
    response = harness.client.post("/v1/context", json={"day": day}, headers=harness.headers())
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("day", ["9999-12-30", "0001-01-02"])
def test_context_accepts_neighboring_representable_day_boundaries(harness, day):
    response = harness.client.post("/v1/context", json={"day": day}, headers=harness.headers())
    assert response.status_code == 200, response.text


def test_text_patch_preserves_sharing_expiry_and_procedure_steps(harness):
    h = harness
    body = MemoryWrite(
        kind="procedure",
        key="dinner",
        text="Original dinner",
        visibility="household",
        validUntil=h.clock() + 600,
        steps=[{"capability": "commerce.meals", "instruction": "Prepare dinner"}],
    ).model_dump()
    grant = h.grant("POST /v1/memories", body)
    response = h.client.post("/v1/memories", json=body, headers=h.headers(grant=grant))
    assert response.status_code == 201
    mid = response.json()["id"]
    response = h.client.patch(
        f"/v1/memories/{mid}", json={"text": "Corrected dinner"}, headers=h.headers(version=1)
    )
    assert response.status_code == 200, response.text
    assert response.json()["steps"] == body["steps"]
    assert response.json()["visibility"] == "household"
    assert response.json()["validUntil"] == body["validUntil"]
    assert h.client.get(f"/v1/memories/{mid}", headers=h.headers("sam")).status_code == 200
    response = h.client.patch(
        f"/v1/memories/{mid}",
        json={"text": "Permanent dinner", "validUntil": None},
        headers=h.headers(version=2),
    )
    assert response.status_code == 200 and response.json()["validUntil"] is None
    assert (
        h.client.patch(
            f"/v1/memories/{mid}",
            json={"text": "No steps", "steps": []},
            headers=h.headers(version=3),
        ).status_code
        == 422
    )


def test_patch_sharing_proof_and_idempotency_bind_only_supplied_fields(harness):
    h = harness
    item = memory(h, validUntil=h.clock() + 600)
    path = f"/v1/memories/{item['id']}"
    body = {"text": "Shared breakfast", "visibility": "household"}
    assert h.client.patch(path, json=body, headers=h.headers(version=1)).status_code == 403
    grant = h.grant(f"PATCH {path}", body, version=1)
    headers = h.headers(version=1, grant=grant)
    response = h.client.patch(path, json=body, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["validUntil"] == item["validUntil"]
    assert h.client.patch(path, json=body, headers=headers).status_code == 200
    assert (
        h.client.patch(path, json={**body, "validUntil": None}, headers=headers).status_code == 409
    )


@pytest.mark.parametrize("kind", ["preference", "procedure"])
def test_expired_key_can_be_replaced_without_old_erasure_releasing_new_slot(harness, kind):
    h = harness
    body = MemoryWrite(
        kind=kind,
        key="dinner",
        text="Original",
        validUntil=h.clock() + 10,
        steps=[{"capability": "commerce.meals", "instruction": "Dinner"}]
        if kind == "procedure"
        else [],
    ).model_dump()
    first = h.client.post("/v1/memories", json=body, headers=h.headers()).json()
    h.clock.advance(11)
    body.update(text="Replacement", validUntil=None)
    response = h.client.post("/v1/memories", json=body, headers=h.headers())
    assert response.status_code == 201, response.text
    second = response.json()
    assert second["id"] != first["id"]
    assert (
        h.client.delete(f"/v1/memories/{first['id']}", headers=h.headers(version=1)).status_code
        == 200
    )
    assert h.client.post("/v1/memories", json=body, headers=h.headers()).status_code == 409
    context = h.client.post("/v1/context", json={"key": "dinner"}, headers=h.headers()).json()
    assert [item["id"] for item in context["items"]] == [second["id"]]


def test_expired_slot_replacement_is_guarded_against_canonical_renewal(harness):
    h = harness
    body = MemoryWrite(
        kind="preference", key="dinner", text="Original", validUntil=h.clock() + 10
    ).model_dump()
    first = h.client.post("/v1/memories", json=body, headers=h.headers()).json()
    h.clock.advance(11)
    service = Memory(h.domain)
    ctx = h.domain.context("alex", h.h)
    replacement, writes, _ = service.create(ctx, {**body, "validUntil": None})
    old = h.domain.store.get("Domain", (hkey(h.h), f"MEMORY#{first['id']}"))
    h.domain.store.transact([put("Domain", revised(old, validUntil=h.clock() + 600), old)])
    with pytest.raises(Conflict):
        h.domain.store.transact(ctx.guards() + writes)
    assert h.domain.store.get("Domain", (hkey(h.h), f"MEMORY#{replacement['id']}")) is None


def test_civil_day_context_spends_archive_bound_on_newest_utc_partition(harness):
    h = harness
    day = "2026-10-04"
    start = int(datetime.fromisoformat(day).replace(tzinfo=ZoneInfo("Europe/Paris")).timestamp())
    h.clock.value = start + 2 * 86400
    item = memory(h, occurredAt=start + 12 * 3600)
    # More than the archive bound in the older UTC slice used to hide the newest slice.
    older_pk = f"MEMDAY#{h.h}#2026-10-03"
    for i in range(501):
        h.domain.store.transact(
            [put("Domain", row(older_pk, f"{start:020d}#{i:04d}", id=f"missing-{i}"))]
        )
    query, scanned = h.domain.store.query, []

    def tracked_query(table, pk, **kwargs):
        page, last = query(table, pk, **kwargs)
        if pk.startswith("MEMDAY#"):
            scanned.extend(page)
        return page, last

    h.domain.store.query = tracked_query
    response = h.client.post("/v1/context", json={"day": day}, headers=h.headers())
    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == item["id"]
    assert response.json()["truncated"] is True
    assert len(scanned) == 500


def test_natural_expiration_purges_ranked_vectors_after_worker_restart(harness):
    h = harness
    expired = [memory(h, validUntil=h.clock() + 10) for _ in range(20)]
    valid = memory(h)
    # Lower-ranked live candidate, below the original top-20 expired candidates.
    assert (
        h.client.patch(
            f"/v1/memories/{valid['id']}",
            json={"text": "Breakfast dinner"},
            headers=h.headers(version=1),
        ).status_code
        == 200
    )
    service = Semantic(h.domain)
    service.mode = "simulated"
    service.sweep()
    service.sweep()
    h.clock.advance(11)
    restarted = Semantic(h.domain)
    restarted.mode = "simulated"
    restarted.sweep()
    assert [
        item["id"] for item in restarted.search(h.domain.context("alex", h.h), "Breakfast tomorrow")
    ] == [valid["id"]]
    assert all(
        h.domain.store.get("Domain", (f"VECTOR#{h.h}", f"MEMORY#{x['id']}"))["deleted"]
        for x in expired
    )


def test_legacy_done_vectors_are_repaired_on_recall_then_purged_after_restart(harness):
    h = harness
    expired = [memory(h, validUntil=h.clock() + 10) for _ in range(20)]
    valid = memory(h)
    assert (
        h.client.patch(
            f"/v1/memories/{valid['id']}",
            json={"text": "Breakfast dinner"},
            headers=h.headers(version=1),
        ).status_code
        == 200
    )
    service = Semantic(h.domain)
    service.mode = "simulated"
    service.sweep()
    service.sweep()
    # Reproduce the published worker's DONE records, without an expiration schedule.
    for item in expired:
        intent = h.domain.store.get("Delivery", (f"MEMINDEX#{item['id']}", "META"))
        done = h.domain.done_intent(intent)
        done.pop("dueAt", None)
        h.domain.store.transact([put("Delivery", done, intent)])
    h.clock.advance(11)
    ctx = h.domain.context("alex", h.h)
    assert service.sweep() == 0
    assert service.search(ctx, "Breakfast tomorrow") == []
    restarted = Semantic(h.domain)
    restarted.mode = "simulated"
    assert restarted.sweep() == 20
    assert [item["id"] for item in restarted.search(ctx, "Breakfast tomorrow")] == [valid["id"]]


def test_legacy_expiration_repair_loses_to_concurrent_renewal(harness):
    h = harness
    item = memory(h, validUntil=h.clock() + 10)
    service = Semantic(h.domain)
    service.mode = "simulated"
    service.sweep()
    key = (f"MEMINDEX#{item['id']}", "META")
    intent = h.domain.store.get("Delivery", key)
    h.domain.store.transact([put("Delivery", h.domain.done_intent(intent), intent)])
    h.clock.advance(11)
    transact = h.domain.store.transact

    def renew_before_repair(changes):
        current = h.domain.store.get("Domain", (hkey(h.h), f"MEMORY#{item['id']}"))
        latest = h.domain.store.get("Delivery", key)
        renewed = revised(current, validUntil=h.clock() + 600)
        transact(
            [
                put("Domain", renewed, current),
                put("Delivery", Memory(h.domain).index_intent(renewed, latest), latest),
            ]
        )
        transact(changes)

    h.domain.store.transact = renew_before_repair
    service.repair_expired_candidate(h.domain.context("alex", h.h), item["id"])
    h.domain.store.transact = transact
    current = h.domain.store.get("Delivery", key)
    assert current["memoryRev"] == 2 and current["GSI1PK"].startswith("MEMINDEX#")
    service.sweep()
    assert service.search(h.domain.context("alex", h.h), "Breakfast")[0]["rev"] == 2


def test_memories_are_private_by_default_and_shared_requires_fresh_proof(harness):
    h = harness
    private = memory(h)
    for actor, household in (("sam", h.h), ("speaker", h.h), ("robin", h.h2)):
        assert (
            h.client.get(
                f"/v1/memories/{private['id']}", headers=h.headers(actor, h=household)
            ).status_code
            == 404
        )
    body = MemoryWrite(
        kind="preference", key="taste", text="Less sweet", visibility="household"
    ).model_dump()
    assert h.client.post("/v1/memories", json=body, headers=h.headers()).status_code == 403
    shared = memory(h, visibility="household")
    assert (
        h.client.get(f"/v1/memories/{shared['id']}", headers=h.headers("speaker")).status_code
        == 200
    )
    assert (
        h.client.delete(
            f"/v1/memories/{shared['id']}", headers=h.headers("sam", version=1)
        ).status_code
        == 404
    )


def test_correction_and_erasure_win_against_stale_vectors_and_idempotency(harness):
    h = harness
    service = Semantic(h.domain)
    service.mode = "simulated"
    item = memory(h)
    service.sweep()
    ctx = h.domain.context("alex", h.h)
    assert [x["id"] for x in service.search(ctx, "Breakfast")] == [item["id"]]
    body = MemoryPatch(text="Dinner tonight").model_dump()
    assert (
        h.client.patch(
            f"/v1/memories/{item['id']}", json=body, headers=h.headers(version=1)
        ).status_code
        == 200
    )
    assert service.search(ctx, "Breakfast") == []
    service.sweep()
    assert service.search(ctx, "Dinner")[0]["text"] == "Dinner tonight"
    headers = h.headers(version=2)
    assert h.client.delete(f"/v1/memories/{item['id']}", headers=headers).status_code == 200
    assert h.client.delete(f"/v1/memories/{item['id']}", headers=headers).status_code == 200
    assert service.search(ctx, "Dinner") == []
    service.sweep()
    assert h.client.get(f"/v1/memories/{item['id']}", headers=h.headers()).status_code == 404
    # Neither mutation idempotency receipts nor the erased canonical record retain text.
    sessions = json.dumps(
        [
            v
            for (t, _), v in h.domain.store.rows.items()
            if t == "Sessions" and v["PK"].startswith("IDEMP2#")
        ]
    )
    assert "Breakfast" not in sessions and "Dinner tonight" not in sessions
    erased = h.domain.store.get("Domain", (hkey(h.h), f"MEMORY#{item['id']}"))
    assert erased["text"] == "" and erased["steps"] == []


def test_replayed_projection_and_cross_scope_candidates_cannot_leak(harness):
    h = harness
    item = memory(h)
    service = Semantic(h.domain)
    service.mode = "simulated"
    pending = service.pending("MEMINDEX")[0]
    service.project(pending)
    ctx = h.domain.context("sam", h.h)
    assert service.search(ctx, "Breakfast") == []
    h.client.delete(f"/v1/memories/{item['id']}", headers=h.headers(version=1))
    service.project(pending)
    assert service.search(h.domain.context("alex", h.h), "Breakfast") == []


@pytest.mark.parametrize("day,length", [("2026-03-29", 23), ("2026-10-25", 25)])
def test_yesterday_uses_civil_day_across_daylight_saving(harness, day, length):
    h = harness
    zone = ZoneInfo("Europe/Paris")
    reference = datetime.fromisoformat(day).replace(tzinfo=zone)
    h.clock.value = int(reference.timestamp()) + length * 3600 + 3600
    item = memory(h, occurredAt=int(reference.timestamp()) + 3600)
    service = Memory(h.domain)
    body = {"day": "yesterday", "key": None, "query": None, "limit": 8, "maxCharacters": 8000}
    context = service.context(h.domain.context("alex", h.h), body)
    assert context["range"]["end"] - context["range"]["start"] == length * 3600
    assert context["items"][0]["id"] == item["id"]


def test_context_reads_current_task_state_and_reports_absent_source(harness):
    h = harness
    tid = h.command()
    item = memory(h, source={"kind": "task", "id": tid})
    h.engine.run(h.h, tid)
    response = h.client.post("/v1/context", json={}, headers=h.headers())
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["linkedState"]["status"] == "SUCCEEDED"
    current = h.domain.store.get("Domain", (hkey(h.h), f"TASK#{tid}"))
    h.domain.store.transact(
        [put("Domain", revised(current, owner="sam", visibility="private"), current)]
    )
    response = h.client.post("/v1/context", json={}, headers=h.headers())
    assert response.json()["items"][0]["sourceStatus"] == "absent"
    assert item["id"] in response.json()["missingSources"]


def test_preference_unique_key_version_expiration_and_declarative_procedure(harness):
    h = harness
    body = MemoryWrite(
        kind="preference", key="taste", text="Less sweet", validUntil=h.clock() + 10
    ).model_dump()
    response = h.client.post("/v1/memories", json=body, headers=h.headers())
    assert response.status_code == 201
    assert h.client.post("/v1/memories", json=body, headers=h.headers()).status_code == 409
    mid = response.json()["id"]
    assert (
        h.client.patch(
            f"/v1/memories/{mid}", json={"text": "More sweet"}, headers=h.headers(version=99)
        ).status_code
        == 412
    )
    h.clock.advance(11)
    assert h.client.get(f"/v1/memories/{mid}", headers=h.headers()).status_code == 404
    assert (
        h.client.post(
            "/v1/memories",
            json={"kind": "commitment", "text": "Purchase succeeded"},
            headers=h.headers(),
        ).status_code
        == 422
    )
    assert (
        h.client.post(
            "/v1/memories",
            json={
                "kind": "procedure",
                "key": "meal",
                "text": "Dinner",
                "steps": [{"capability": "shell.execute", "instruction": "Do it"}],
            },
            headers=h.headers(),
        ).status_code
        == 422
    )


def test_index_write_racing_correction_leaves_current_intent_pending(harness):
    h = harness
    item = memory(h)
    service = Semantic(h.domain)
    service.mode = "simulated"
    embed = service.embed

    def race(text):
        h.client.patch(
            f"/v1/memories/{item['id']}", json={"text": "New dinner"}, headers=h.headers(version=1)
        )
        return embed(text)

    service.embed = race
    service.sweep()
    assert service.pending("MEMINDEX")[0]["memoryRev"] == 2
    service.embed = embed
    service.sweep()
    assert service.search(h.domain.context("alex", h.h), "New dinner")[0]["rev"] == 2


def test_invalid_mode_fields_and_private_source_share_are_refused(harness):
    h = harness
    item = memory(h)
    assert (
        h.client.post(
            "/v1/memories",
            json={"kind": "exchange", "text": "x", "owner": "sam"},
            headers=h.headers(),
        ).status_code
        == 422
    )
    body = MemoryWrite(
        kind="exchange",
        text="Copy",
        visibility="household",
        source={"kind": "memory", "id": item["id"]},
    ).model_dump()
    assert h.client.post("/v1/memories", json=body, headers=h.headers()).status_code == 403
    with pytest.raises(ValueError):
        replace(h.settings, env="prod", semantic_mode="simulated")
