import json
from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from stage2_helpers import memory

from koyori.domain import hkey
from koyori.memory import Memory
from koyori.semantic import Semantic
from koyori.stage2_contracts import MemoryPatch, MemoryWrite
from koyori.store import put, revised


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
