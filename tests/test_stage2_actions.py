from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from stage2_helpers import approve, commerce, quote, reserve

from koyori.actions import CATALOG, Actions, Simulator, UnknownOutcome
from koyori.domain import row
from koyori.errors import Conflict, Problem
from koyori.stage2_contracts import BudgetPut
from koyori.store import put


def test_legacy_members_without_access_epoch_can_use_new_connectors(harness):
    h = harness
    current = h.domain.context("alex", h.h).member
    legacy = {k: v for k, v in current.items() if k != "accessEpoch"}
    h.domain.store.transact([put("Domain", legacy, current)])
    connection = commerce(h)
    action = reserve(h, quote(h, connection))
    service = Actions(h.domain)
    service.run(h.h, action["id"])
    assert (
        service.get(h.domain.context("alex", h.h), "ACTION", action["id"])["status"] == "CONFIRMED"
    )


def test_authenticated_provider_notifications_are_hints_with_replay_control(harness):
    from koyori.stage2_contracts import SupplierNotice

    h = harness
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
    service = Actions(h.domain)
    service.run(h.h, action["id"])
    raw = service.get(h.domain.context("alex", h.h), "ACTION", action["id"])
    payload = SupplierNotice(
        eventId=uuid4().hex, householdId=h.h, actionId=action["id"], occurredAt=h.clock()
    ).model_dump()
    signature = service.notification_signature(raw, payload)
    assert (
        h.client.post(
            "/v1/webhooks/commerce-simulator", json=payload, headers={"X-Koyori-Signature": "wrong"}
        ).status_code
        == 403
    )
    assert (
        h.client.post(
            "/v1/webhooks/commerce-simulator",
            json=payload,
            headers={"X-Koyori-Signature": signature},
        ).status_code
        == 204
    )
    intent = h.domain.store.get("Delivery", (f"ACTIONRUN#{action['id']}", "META"))
    assert (
        h.client.post(
            "/v1/webhooks/commerce-simulator",
            json=payload,
            headers={"X-Koyori-Signature": signature},
        ).status_code
        == 204
    )
    assert h.domain.store.get("Delivery", (intent["PK"], intent["SK"]))["rev"] == intent["rev"]
    assert service.get(h.domain.context("alex", h.h), "ACTION", action["id"])["status"] == "UNKNOWN"
    service.run(h.h, action["id"])
    assert (
        service.get(h.domain.context("alex", h.h), "ACTION", action["id"])["status"] == "CONFIRMED"
    )


def test_quote_expiration_prevents_a_queued_send(harness):
    h = harness
    connection = commerce(h)
    action = reserve(h, quote(h, connection))
    h.clock.advance(121)
    service = Actions(h.domain)
    service.run(h.h, action["id"])
    current = service.get(h.domain.context("alex", h.h), "ACTION", action["id"])
    assert current["status"] == "BLOCKED" and service.provider.lookup(current) is None
    assert service.budget(h.domain.context("alex", h.h))["heldMinor"] == 0


def test_explicit_action_is_durable_idempotent_and_receipt_is_simulated(harness):
    h = harness
    connection = commerce(h)
    q = quote(h, connection)
    headers = h.headers()
    action = reserve(h, q, headers=headers)
    assert reserve(h, q, headers=headers)["id"] == action["id"]
    assert h.client.get(f"/v1/actions/{action['id']}", headers=h.headers("sam")).status_code == 404
    Actions(h.domain).run(h.h, action["id"])
    current = h.client.get(f"/v1/actions/{action['id']}", headers=h.headers()).json()
    assert current["status"] == "CONFIRMED" and current["receipt"]["kind"] == "simulated"
    assert current["receipt"]["totalMinor"] == 180
    budget = h.client.get("/v1/budget", headers=h.headers()).json()
    assert budget["spentMinor"] == 180 and budget["heldMinor"] == 0
    assert (
        h.client.post("/v1/actions", json={"quoteId": q["id"]}, headers=h.headers()).status_code
        == 409
    )


def test_approval_exact_terms_and_policy_changes(harness):
    h = harness
    connection = commerce(h, approval=True)
    q = quote(h, connection)
    assert (
        h.client.post("/v1/actions", json={"quoteId": q["id"]}, headers=h.headers()).status_code
        == 403
    )
    approval = approve(h, q)
    another = quote(h, connection, quantity=2)
    assert (
        h.client.post(
            "/v1/actions",
            json={"quoteId": another["id"], "approvalId": approval["id"]},
            headers=h.headers(),
        ).status_code
        == 409
    )
    budget = h.client.get("/v1/budget", headers=h.headers()).json()
    body = BudgetPut(limitMinor=10000, perActionMinor=5000, approvalRequired=True).model_dump()
    assert (
        h.client.put("/v1/budget", json=body, headers=h.headers(version=budget["rev"])).status_code
        == 200
    )
    assert (
        h.client.post(
            "/v1/actions",
            json={"quoteId": q["id"], "approvalId": approval["id"]},
            headers=h.headers(),
        ).status_code
        == 409
    )


def test_price_change_invalidates_approval_and_mode_cannot_be_selected(harness):
    h = harness
    connection = commerce(h, approval=True)
    q = quote(h, connection)
    approved = approve(h, q)
    h.domain.store.transact(
        [
            put(
                "Domain",
                row("PROVIDER#commerce-simulator", prices={**CATALOG, "milk": 200}, fault="none"),
            )
        ]
    )
    assert (
        h.client.post(
            "/v1/actions",
            json={"quoteId": q["id"], "approvalId": approved["id"]},
            headers=h.headers(),
        ).json()["code"]
        == "QUOTE_CHANGED"
    )
    assert (
        h.client.post(
            "/v1/connections/simulated", json={"mode": "real"}, headers=h.headers()
        ).status_code
        == 422
    )
    assert (
        h.client.post(
            "/v1/actions", json={"quoteId": q["id"], "mode": "real"}, headers=h.headers()
        ).status_code
        == 422
    )


def test_two_concurrent_reservations_cannot_overspend(harness):
    h = harness
    connection = commerce(h, limit=180)
    quotes = [quote(h, connection), quote(h, connection)]

    def attempt(q):
        service = Actions(h.domain)
        ctx = h.domain.context("alex", h.h)
        try:
            return service.mutate(
                ctx,
                "POST /v1/actions",
                {"quoteId": q["id"]},
                uuid4().hex,
                None,
                None,
                lambda fresh: service.reserve(fresh, {"quoteId": q["id"]}),
            )
        except Problem as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, quotes))
    assert sum(isinstance(x, dict) for x in results) == 1
    assert "BUDGET_EXCEEDED" in results
    assert Actions(h.domain).budget(h.domain.context("alex", h.h))["heldMinor"] == 180


def test_response_lost_after_provider_commit_reconciles_once_even_after_revocation(harness):
    h = harness
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
    service = Actions(h.domain)
    service.run(h.h, action["id"])
    current = service.get(h.domain.context("alex", h.h), "ACTION", action["id"])
    assert current["status"] == "UNKNOWN" and current["heldMinor"] == 180
    assert (
        h.client.delete(
            f"/v1/connections/{connection['id']}", headers=h.headers(version=1)
        ).status_code
        == 200
    )
    h.clock.advance(6)
    service.run(h.h, action["id"])
    current = service.get(h.domain.context("alex", h.h), "ACTION", action["id"])
    assert current["status"] == "CONFIRMED"
    provider_rows = [
        v
        for (t, k), v in h.domain.store.rows.items()
        if t == "Domain" and k[0].startswith("SIMOP#")
    ]
    assert len(provider_rows) == 1
    assert service.budget(h.domain.context("alex", h.h))["heldMinor"] == 0


def test_revocation_blocks_ready_send_and_releases_only_unsent_reservation(harness):
    h = harness
    connection = commerce(h)
    action = reserve(h, quote(h, connection))
    h.client.delete(f"/v1/connections/{connection['id']}", headers=h.headers(version=1))
    service = Actions(h.domain)
    service.run(h.h, action["id"])
    assert service.get(h.domain.context("alex", h.h), "ACTION", action["id"])["status"] == "BLOCKED"
    assert (
        service.provider.lookup(service.get(h.domain.context("alex", h.h), "ACTION", action["id"]))
        is None
    )
    assert service.budget(h.domain.context("alex", h.h))["heldMinor"] == 0


def test_modify_and_cancel_have_separate_evidence_and_correct_budget(harness):
    h = harness
    connection = commerce(h)
    service = Actions(h.domain)
    q = quote(h, connection, quantity=2)
    action = reserve(h, q)
    service.run(h.h, action["id"])
    modify = reserve(
        h,
        quote(
            h,
            connection,
            quantity=1,
            intention=q["conditions"]["intentionId"],
            operation="modify",
            target=action["id"],
        ),
    )
    service.run(h.h, modify["id"])
    assert service.budget(h.domain.context("alex", h.h))["spentMinor"] == 180
    cancel = reserve(
        h,
        quote(
            h,
            connection,
            intention=q["conditions"]["intentionId"],
            operation="cancel",
            target=modify["id"],
        ),
    )
    service.run(h.h, cancel["id"])
    current = service.get(h.domain.context("alex", h.h), "ACTION", cancel["id"])
    assert current["status"] == "CANCELLED" and current["receipt"]["status"] == "CANCELLED"
    assert current["receipt"]["operationId"] != modify["id"]
    assert service.budget(h.domain.context("alex", h.h))["spentMinor"] == 0


def test_crash_after_send_before_recording_receipt_keeps_fencing_and_reservation(harness):
    h = harness
    connection = commerce(h)
    action = reserve(h, quote(h, connection))
    service = Actions(h.domain)
    finish = service._finish

    def crash(*args):
        raise RuntimeError("process exit")

    service._finish = crash
    with pytest.raises(RuntimeError):
        service.run(h.h, action["id"])
    assert (
        service.get(h.domain.context("alex", h.h), "ACTION", action["id"])["status"]
        == "DISPATCHING"
    )
    h.clock.advance(31)
    service._finish = finish
    service.run(h.h, action["id"])
    current = service.get(h.domain.context("alex", h.h), "ACTION", action["id"])
    service._finish({**current, "runEpoch": current["runEpoch"] - 1}, {})
    assert current["status"] == "CONFIRMED"


def test_unknown_without_evidence_is_never_resent_and_cannot_be_replaced(harness):
    h = harness
    connection = commerce(h)
    q = quote(h, connection)
    action = reserve(h, q)

    class NoEvidence(Simulator):
        sends = 0

        def execute(self, action):
            self.sends += 1
            raise UnknownOutcome

    provider = NoEvidence(h.domain)
    service = Actions(h.domain, provider)
    service.run(h.h, action["id"])
    h.clock.advance(6)
    service.run(h.h, action["id"])
    assert provider.sends == 1
    assert service.budget(h.domain.context("alex", h.h))["heldMinor"] == 180
    with pytest.raises(Problem, match="TARGET_UNRESOLVED"):
        service.quote(
            h.domain.context("alex", h.h),
            {
                **q["conditions"],
                "connectionId": connection["id"],
                "targetActionId": action["id"],
                "operation": "cancel",
                "lines": [],
            },
        )


def test_reservation_rolls_back_with_revoked_authority_snapshot(harness):
    h = harness
    connection = commerce(h)
    q = quote(h, connection)
    service = Actions(h.domain)
    ctx = h.domain.context("alex", h.h)
    _, writes, _ = service.reserve(ctx, {"quoteId": q["id"]})
    _, revocation, _ = service.revoke(ctx, connection["id"], 1)
    h.domain.store.transact(ctx.guards() + revocation)
    with pytest.raises(Conflict):
        h.domain.store.transact(ctx.guards() + writes)
    assert service.budget(ctx)["heldMinor"] == 0
