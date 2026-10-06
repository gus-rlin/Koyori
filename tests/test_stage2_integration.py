"""Stage-two invariants against actual DynamoDB Local transactions, not AWS qualification."""

from dataclasses import replace

import pytest
from stage2_helpers import commerce, memory, quote, reserve
from test_stage2_calendar import FakeGoogle, connect
from test_stage2_semantic_adapters import BedrockFixture

from koyori.actions import CATALOG, Actions
from koyori.calendar import Calendar
from koyori.domain import hkey, row
from koyori.errors import Conflict
from koyori.memory import Memory
from koyori.semantic import Semantic
from koyori.stage2_contracts import MemoryWrite
from koyori.store import put, revised

pytestmark = pytest.mark.integration
pytest_plugins = ["test_integration"]


def test_dynamo_pending_watch_and_lost_membership_cleanup_survive_restart(dynamo):
    h = dynamo
    h.domain.settings = replace(
        h.settings,
        google_client_id="fixture-google",
        google_redirect_uri="http://127.0.0.1/callback",
        google_webhook_url="https://example.invalid/hook",
    )
    service = h.client.app.state.calendar
    service.google = FakeGoogle(h.clock)
    connection, _ = connect(h, service)
    watch = service.google.watch

    class WorkerKilled(BaseException):
        pass

    def lost_reply(*args, **kwargs):
        watch(*args, **kwargs)
        raise WorkerKilled()

    service.google.watch = lost_reply
    with pytest.raises(WorkerKilled):
        service.register_watch(h.domain.context("alex", h.h), connection["id"])
    service.google.watch = watch
    restarted = Calendar(h.domain, google=service.google, envelope=service.envelope)
    assert restarted.register_watch(h.domain.context("alex", h.h), connection["id"]) == 0
    assert len(service.google.watches) == 1
    member = h.domain.store.get("Domain", (hkey(h.h), "MEMBER#alex"))
    h.domain.store.transact([put("Domain", revised(member, active=False), member)])
    restarted.sweep()
    current = h.domain.store.get("Domain", (hkey(h.h), f"CONNECTION#{connection['id']}"))
    assert not current["active"] and current["revokePending"]
    restarted.sweep()
    assert h.domain.store.get("Connections", restarted.token_key(current))["envelope"] is None
    assert service.google.revoked and restarted.sweep() == 0


def test_dynamo_disabled_projection_completes_pending_memory_work(dynamo):
    h = dynamo
    items = [memory(h) for _ in range(3)]
    assert (
        h.client.delete(f"/v1/memories/{items[0]['id']}", headers=h.headers(version=1)).status_code
        == 200
    )
    service = Semantic(h.domain)
    service.mode = "disabled"
    assert service.sweep() == 3
    assert service.sweep() == 0
    assert all(
        h.domain.store.get("Delivery", (f"MEMINDEX#{x['id']}", "META"))["status"] == "DONE"
        for x in items
    )


def test_dynamo_expired_key_replacement_guards_slot_and_canonical_record(dynamo):
    h = dynamo
    body = MemoryWrite(
        kind="preference", key="dinner", text="Original", validUntil=h.clock() + 10
    ).model_dump()
    response = h.client.post("/v1/memories", json=body, headers=h.headers())
    assert response.status_code == 201
    first = response.json()
    h.clock.advance(11)
    service = Memory(h.domain)
    ctx = h.domain.context("alex", h.h)
    body["validUntil"] = None
    replacements = [service.create(ctx, body) for _ in range(2)]
    h.domain.store.transact(ctx.guards() + replacements[0][1])
    with pytest.raises(Conflict):
        h.domain.store.transact(ctx.guards() + replacements[1][1])
    assert (
        h.client.delete(f"/v1/memories/{first['id']}", headers=h.headers(version=1)).status_code
        == 200
    )
    assert h.client.post("/v1/memories", json=body, headers=h.headers()).status_code == 409

    # A canonical renewal also invalidates a prepared replacement transaction.
    response = h.client.post(
        "/v1/memories",
        json={**body, "key": "breakfast", "validUntil": h.clock() + 10},
        headers=h.headers(),
    )
    assert response.status_code == 201
    h.clock.advance(11)
    _, writes, _ = service.create(ctx, {**body, "key": "breakfast"})
    old = h.domain.store.get("Domain", (hkey(h.h), f"MEMORY#{response.json()['id']}"))
    h.domain.store.transact([put("Domain", revised(old, validUntil=h.clock() + 600), old)])
    with pytest.raises(Conflict):
        h.domain.store.transact(ctx.guards() + writes)

    # Inverse race: a renewal prepared before expiry loses after slot replacement.
    response = h.client.post(
        "/v1/memories",
        json={**body, "key": "tea", "validUntil": h.clock() + 10},
        headers=h.headers(),
    )
    assert response.status_code == 201
    mid = response.json()["id"]
    _, renewal, _ = service.change(
        ctx, mid, {"text": "Renewed tea", "validUntil": h.clock() + 600}, 1
    )
    h.clock.advance(11)
    response = h.client.post("/v1/memories", json={**body, "key": "tea"}, headers=h.headers())
    assert response.status_code == 201
    with pytest.raises(Conflict):
        h.domain.store.transact(ctx.guards() + renewal)


def test_dynamo_memory_chronology_correction_and_erasure(dynamo):
    h = dynamo
    first = memory(h, occurredAt=h.clock() - 60)
    second = memory(h, occurredAt=h.clock() - 30)
    listed = h.client.get("/v1/memories", headers=h.headers()).json()
    assert [item["id"] for item in listed["items"]] == [first["id"], second["id"]]
    context = h.client.post("/v1/context", json={}, headers=h.headers()).json()
    assert [item["id"] for item in context["items"]] == [second["id"], first["id"]]
    semantic = Semantic(h.domain)
    semantic.mode = "simulated"
    semantic.sweep()
    assert (
        h.client.patch(
            f"/v1/memories/{first['id']}", json={"text": "New dinner"}, headers=h.headers(version=1)
        ).status_code
        == 200
    )
    assert (
        h.client.delete(f"/v1/memories/{second['id']}", headers=h.headers(version=1)).status_code
        == 200
    )
    assert semantic.search(h.domain.context("alex", h.h), "Breakfast") == []
    semantic.sweep()
    assert semantic.search(h.domain.context("alex", h.h), "dinner")[0]["id"] == first["id"]


def test_dynamo_parallel_budget_snapshots_roll_back_entire_losing_action(dynamo):
    h = dynamo
    connection = commerce(h, limit=180)
    quotes = [quote(h, connection), quote(h, connection)]
    actions = Actions(h.domain)
    ctx = h.domain.context("alex", h.h)
    responses = [actions.reserve(ctx, {"quoteId": q["id"]}) for q in quotes]
    h.domain.store.transact(ctx.guards() + responses[0][1])
    with pytest.raises(Conflict):
        h.domain.store.transact(ctx.guards() + responses[1][1])
    assert h.domain.store.get("Domain", (hkey(h.h), f"ACTION#{responses[1][0]['id']}")) is None
    assert h.domain.store.get("Delivery", (f"ACTIONRUN#{responses[1][0]['id']}", "META")) is None
    assert actions.budget(ctx)["heldMinor"] == 180


def test_dynamo_lost_response_new_worker_reconciles_same_provider_operation(dynamo):
    h = dynamo
    connection = commerce(h)
    h.domain.store.transact(
        [
            put(
                "Domain",
                row("PROVIDER#commerce-simulator", prices=CATALOG, fault="timeout-after-commit"),
            )
        ]
    )
    action = reserve(h, quote(h, connection))
    Actions(h.domain).run(h.h, action["id"])
    h.clock.advance(6)
    restarted = Actions(h.domain)
    restarted.sweep()
    current = restarted.get(h.domain.context("alex", h.h), "ACTION", action["id"])
    assert current["status"] == "CONFIRMED"
    assert current["receipt"]["operationId"] == action["id"]
    assert restarted.budget(h.domain.context("alex", h.h))["spentMinor"] == 180


def test_dynamo_interrupted_external_projection_repairs_completed_erasure(dynamo):
    h = dynamo
    item = memory(h)
    key = (f"MEMINDEX#{item['id']}", "META")

    class WorkerKilled(BaseException):
        pass

    class Vectors:
        present = False

        def put_vectors(self, **args):
            assert (
                h.client.delete(
                    f"/v1/memories/{item['id']}", headers=h.headers(version=1)
                ).status_code
                == 200
            )
            service.project(h.domain.store.get("Delivery", key))
            assert h.domain.store.get("Delivery", key)["status"] == "DONE"
            self.present = True
            raise WorkerKilled()

        def delete_vectors(self, **args):
            self.present = False

    vectors = Vectors()
    service = Semantic(h.domain, bedrock=BedrockFixture(), vectors=vectors)
    service.mode = "aws"
    with pytest.raises(WorkerKilled):
        service.project(h.domain.store.get("Delivery", key))
    assert vectors.present
    h.clock.advance(121)
    restarted = Semantic(h.domain, bedrock=BedrockFixture(), vectors=vectors)
    restarted.mode = "aws"
    restarted.sweep()
    assert not vectors.present and h.domain.store.get("Delivery", key)["status"] == "DONE"
