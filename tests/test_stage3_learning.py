from datetime import UTC, datetime

from stage2_helpers import commerce, memory
from stage3_helpers import goals, progress, submit

from koyori.actions import Actions
from koyori.notifications import Notifications, delivery_time
from koyori.stage3_contracts import LearningSubmit, NotificationPolicy


def test_feedback_acceptance_changes_proposals_without_increasing_authority(harness):
    h = harness
    commerce(h)
    budget = h.client.get("/v1/budget", headers=h.headers()).json()
    body = LearningSubmit(
        text="Je préfère un dîner végétarien",
        kind="preference",
        key="dinner",
        source={"kind": "declaration"},
    ).model_dump()
    response = h.client.post("/v1/learning", json=body, headers=h.headers())
    assert response.status_code == 201, response.text
    proposal = response.json()
    assert (
        h.client.post("/v1/context", json={"key": "dinner"}, headers=h.headers()).json()["items"]
        == []
    )
    accepted = h.client.post(
        f"/v1/learning/{proposal['id']}/decisions",
        json={"decision": "accept"},
        headers=h.headers(version=proposal["rev"]),
    )
    assert accepted.status_code == 200, accepted.text
    assert h.client.get("/v1/budget", headers=h.headers()).json() == budget
    tid = submit(h)
    done = progress(h, tid, goals(h))
    assert done["status"] == "SUCCEEDED", done
    assert done["stepStates"]["dinner"]["receipt"]
    action = Actions(h.domain).get(
        h.domain.context("alex", h.h), "ACTION", done["intents"]["dinner"]["actions"][0]
    )
    assert action["conditions"]["lines"][0]["sku"] == "vegetarian-meal"


def test_sourced_proposal_cannot_accept_after_source_erasure(harness):
    h = harness
    source = memory(h)
    body = LearningSubmit(
        text="Less sweet",
        kind="preference",
        key="sweetness",
        source={"kind": "memory", "id": source["id"]},
    ).model_dump()
    response = h.client.post("/v1/learning", json=body, headers=h.headers())
    proposal = response.json()
    assert (
        h.client.delete(
            f"/v1/memories/{source['id']}", headers=h.headers(version=source["rev"])
        ).status_code
        == 200
    )
    decision = h.client.post(
        f"/v1/learning/{proposal['id']}/decisions",
        json={"decision": "accept"},
        headers=h.headers(version=proposal["rev"]),
    )
    assert decision.status_code == 404
    assert h.client.get(f"/v1/learning/{proposal['id']}", headers=h.headers()).json()["text"] == ""


def test_procedure_has_fixed_declarative_capabilities_and_private_owner(harness):
    h = harness
    body = {
        "text": "Run a command",
        "kind": "procedure",
        "key": "meal",
        "source": {"kind": "declaration"},
        "steps": [{"capability": "shell.run", "instruction": "execute"}],
    }
    assert h.client.post("/v1/learning", json=body, headers=h.headers()).status_code == 422
    body["steps"][0]["capability"] = "commerce.meals"
    created = h.client.post("/v1/learning", json=body, headers=h.headers()).json()
    assert (
        h.client.get(f"/v1/learning/{created['id']}", headers=h.headers("sam")).status_code == 404
    )
    assert h.client.get("/v1/learning", headers=h.headers("speaker")).status_code == 403


def test_notifications_group_and_revalidate_quiet_hours(harness):
    h = harness
    # Direct domain calls let the civil clock vary without forging fresh authentication timestamps.
    h.clock.value = int(datetime(2026, 10, 6, 20, 30, tzinfo=UTC).timestamp())
    ctx = h.domain.context("alex", h.h)
    service = Notifications(h.domain)
    policy = NotificationPolicy(groupSeconds=60).model_dump()
    _, writes, _ = service.configure(ctx, policy, 0)
    h.domain.store.transact(ctx.guards() + writes)
    expected = int(datetime(2026, 10, 7, 6, tzinfo=UTC).timestamp())
    assert delivery_time(h.clock(), policy) == expected
    first = submit(h)
    second = submit(h, "Consulte ma journée")
    for tid in (first, second):
        h.domain.store.transact(service.queue(ctx, "goal", tid, "READY"))
    service.sweep()
    records, _ = h.domain.store.query("Delivery", f"NOTIFY#{h.h}#alex", prefix="BATCH#")
    assert len(records) == 1 and len(records[0]["entries"]) == 2
    assert records[0]["status"] == "PENDING"
    h.clock.value = expected
    service.sweep()
    assert len(service.list(h.domain.context("alex", h.h))["items"]) == 1
    assert service.list(h.domain.context("sam", h.h))["items"] == []


def test_notification_overflow_keeps_every_object_in_bounded_groups(harness):
    h = harness
    ctx = h.domain.context("alex", h.h)
    service = Notifications(h.domain)
    ids = [submit(h, "Consulte ma journée") for _ in range(17)]
    for tid in ids:
        h.domain.store.transact(service.queue(h.domain.context("alex", h.h), "goal", tid, "READY"))
    records, _ = h.domain.store.query("Delivery", f"NOTIFY#{ctx.h}#alex", prefix="BATCH#")
    assert len(records) == 2 and max(len(r["entries"]) for r in records) == 16
    assert {entry["id"] for r in records for entry in r["entries"]} == set(ids)


def test_notification_policy_can_be_created_from_initial_etag_then_requires_current_revision(
    harness,
):
    h = harness
    current = h.client.get("/v1/notification-policy", headers=h.headers()).json()
    assert current["rev"] == 0
    body = NotificationPolicy(groupSeconds=0).model_dump()
    created = h.client.put("/v1/notification-policy", json=body, headers=h.headers(version=0))
    assert created.status_code == 200 and created.json()["rev"] == 1
    assert (
        h.client.put("/v1/notification-policy", json=body, headers=h.headers(version=0)).status_code
        == 412
    )
