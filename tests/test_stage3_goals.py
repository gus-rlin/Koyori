import copy

import pytest
from stage2_helpers import approve, commerce
from stage3_helpers import control, goals, progress, submit, task

from koyori.actions import Actions
from koyori.errors import Problem
from koyori.goals import Goals
from koyori.planner import SimulatedPlanner
from koyori.plans import validate_plan
from koyori.stage3_contracts import Plan


def test_natural_goal_persists_plan_steps_and_simulated_receipt(harness):
    h = harness
    commerce(h)
    service = goals(h)
    tid = submit(h)
    done = progress(h, tid, service)
    assert done["status"] == "SUCCEEDED", done
    assert done["model"]["mode"] == "simulated"
    assert done["modelCalls"] == 1
    assert done["planRevision"] == 1
    assert done["stepStates"]["dinner"]["receipt"]["kind"] == "simulated"
    assert h.domain.context("alex", h.h).household["activeTasks"] == 0
    assert h.engine.acquire(h.h, tid) is None
    assert (
        h.client.post(f"/v1/tasks/{tid}/pause", headers=h.headers(version=done["rev"])).status_code
        == 409
    )


def test_goal_idempotency_and_owner_channel_isolation(harness):
    h = harness
    tid = submit(h, key="a" * 32)
    assert submit(h, key="a" * 32) == tid
    assert (
        h.client.post(
            "/v1/goals", json={"text": "Different goal"}, headers=h.headers(key="a" * 32)
        ).status_code
        == 409
    )
    for principal in ("sam", "speaker", "robin"):
        response = h.client.get(
            f"/v1/goals/{tid}",
            headers=h.headers(principal, h=h.h2 if principal == "robin" else h.h),
        )
        assert response.status_code in {403, 404}
    assert (
        h.client.post(
            "/v1/goals", json={"text": "Buy food", "owner": "sam"}, headers=h.headers()
        ).status_code
        == 422
    )
    assert (
        h.client.post(
            "/v1/goals", json={"text": "Buy food"}, headers=h.headers("speaker")
        ).status_code
        == 403
    )


def test_amend_for_four_modifies_same_commercial_intent(harness):
    h = harness
    commerce(h)
    service = goals(h)
    tid = submit(h)
    first = progress(h, tid, service)
    assert first["status"] == "SUCCEEDED", first
    intent = first["intents"]["dinner"]
    response = h.client.patch(
        f"/v1/goals/{tid}",
        json={"text": "Finalement, prépare le dîner pour quatre demain à 20 h"},
        headers=h.headers(version=first["rev"]),
    )
    assert response.status_code == 200, response.text
    second = progress(h, tid, service)
    assert second["status"] == "SUCCEEDED", second
    assert second["intents"]["dinner"]["intentionId"] == intent["intentionId"]
    first_action, next_action = [
        Actions(h.domain).get(h.domain.context("alex", h.h), "ACTION", aid)
        for aid in second["intents"]["dinner"]["actions"]
    ]
    assert next_action["conditions"]["operation"] == "modify"
    assert next_action["businessId"] == first_action["businessId"]
    assert next_action["conditions"]["lines"][0]["quantity"] == 4


def test_waiting_time_does_not_invoke_model_again(harness):
    h = harness
    commerce(h)
    service = goals(h)
    tid = submit(h)
    for _ in range(4):
        service.sweep()
    waiting = task(h, tid)
    assert waiting["status"] == "WAITING_TIME", waiting
    assert waiting["modelCalls"] == 1
    for _ in range(20):
        service.sweep()
    assert task(h, tid)["modelCalls"] == 1
    h.clock.advance(61)
    done = progress(h, tid, Goals(h.domain, planning=SimulatedPlanner()))
    assert done["status"] == "SUCCEEDED", done
    assert done["modelCalls"] == 1


def test_pause_blocks_reserved_dispatch_and_preserves_unknown_lookup(harness):
    h = harness
    commerce(h)
    service = goals(h)
    tid = submit(h, "Prépare le dîner pour deux demain à 20 h")
    for _ in range(20):
        service.sweep()
        current = task(h, tid)
        if current["intents"].get("dinner", {}).get("actions"):
            break
        h.clock.advance(5)
    assert current["intents"]["dinner"]["actions"]
    aid = current["intents"]["dinner"]["actions"][0]
    control(h, tid, "pause")
    Actions(h.domain).run(h.h, aid)
    assert (
        Actions(h.domain).get(h.domain.context("alex", h.h), "ACTION", aid)["status"] == "BLOCKED"
    )
    assert Actions(h.domain).budget(h.domain.context("alex", h.h))["heldMinor"] == 0


def test_model_output_cannot_forge_tools_accounts_or_success(harness):
    h = harness
    connection = commerce(h)
    ctx = h.domain.context("alex", h.h)
    nominal = {
        "summary": "Dinner",
        "steps": [
            {
                "stepId": "order",
                "kind": "write",
                "capability": "commerce.meals",
                "arguments": {
                    "connectionId": connection["id"],
                    "intentKey": "dinner",
                    "lines": [{"sku": "chicken-meal", "quantity": 2}],
                    "deliveryAt": h.clock() + 3600,
                },
            }
        ],
    }
    validate_plan(
        h.domain, ctx, nominal, allowed_connections={connection["id"]}, allowed_memories=set()
    )
    for bad in (
        {**nominal, "receipt": {"status": "CONFIRMED"}},
        {**nominal, "steps": [{**nominal["steps"][0], "kind": "read"}]},
        {**nominal, "steps": [{**nominal["steps"][0], "capability": "shell.run"}]},
    ):
        with pytest.raises(ValueError):
            Plan.model_validate(bad)
    foreign = copy.deepcopy(nominal)
    foreign["steps"][0]["arguments"]["connectionId"] = "foreign-account"
    with pytest.raises(Problem, match="INVALID_PLAN_ACCOUNT"):
        validate_plan(
            h.domain, ctx, foreign, allowed_connections={connection["id"]}, allowed_memories=set()
        )


def test_invalid_model_repair_and_failure_are_bounded(harness):
    h = harness

    class BadModel:
        mode = "simulated"

        def generate(self, payload, quota, repair=None):
            quota.reserve()
            return {
                "summary": "bad",
                "steps": [{"stepId": "run", "capability": "shell.run", "arguments": {}}],
            }

    service = goals(h)
    service.planning = BadModel()
    tid = submit(h)
    service.sweep()
    failed = task(h, tid)
    assert failed["status"] == "NEEDS_ATTENTION", failed
    assert failed["modelCalls"] == 2
    assert failed["error"] == "INVALID_PLAN"
    for _ in range(20):
        service.sweep()
    assert task(h, tid)["modelCalls"] == 2


def test_cancel_requires_provider_cancellation_receipt(harness):
    h = harness
    commerce(h, approval=False)
    service = goals(h)
    tid = submit(h)
    done = progress(h, tid, service)
    assert done["status"] == "SUCCEEDED", done
    control(h, tid, "cancel")
    cancelled = progress(h, tid, service)
    assert cancelled["status"] == "CANCELLED", cancelled
    actions = cancelled["intents"]["dinner"]["actions"]
    assert len(actions) == 2
    receipt = Actions(h.domain).get(h.domain.context("alex", h.h), "ACTION", actions[-1])["receipt"]
    assert receipt["status"] == "CANCELLED"
    assert Actions(h.domain).budget(h.domain.context("alex", h.h))["spentMinor"] == 0


def test_exact_quote_approval_resumes_goal_and_public_reserve_cannot_bypass_it(harness):
    h = harness
    commerce(h, approval=True)
    service = goals(h)

    class ImmediateRecipe(SimulatedPlanner):
        def generate(self, payload, quota, repair=None):
            plan = super().generate(payload, quota, repair)
            for step in plan["steps"]:
                step["dueAt"] = None
            return plan

    service.planning = ImmediateRecipe()
    tid = submit(h)
    waiting = progress(h, tid, service, advance=False)
    assert waiting["status"] == "WAITING_APPROVAL"
    qid = waiting["stepStates"]["dinner"]["quoteId"]
    assert (
        h.client.post("/v1/actions", json={"quoteId": qid}, headers=h.headers()).status_code == 409
    )
    accepted = approve(h, {"id": qid})
    response = h.client.post(
        f"/v1/goals/{tid}/decisions",
        json={"stepId": "dinner", "approvalId": accepted["id"]},
        headers=h.headers(version=waiting["rev"]),
    )
    assert response.status_code == 202, response.text
    done = progress(h, tid, service)
    assert done["status"] == "SUCCEEDED", done
    assert done["modelCalls"] == 1
    assert Actions(h.domain).get(h.domain.context("alex", h.h), "APPROVAL", accepted["id"])[
        "consumed"
    ]


def test_short_amendment_keeps_delivery_and_business_identity(harness):
    h = harness
    commerce(h)
    service = goals(h)
    tid = submit(h)
    first = progress(h, tid, service)
    response = h.client.patch(
        f"/v1/goals/{tid}",
        json={"text": "Finalement nous serons quatre"},
        headers=h.headers(version=first["rev"]),
    )
    assert response.status_code == 200, response.text
    second = progress(h, tid, service)
    assert second["status"] == "SUCCEEDED", second
    before, after = [
        Actions(h.domain).get(h.domain.context("alex", h.h), "ACTION", aid)
        for aid in second["intents"]["dinner"]["actions"]
    ]
    assert before["conditions"]["deliveryAt"] == after["conditions"]["deliveryAt"]
    assert before["businessId"] == after["businessId"]
    assert after["conditions"]["lines"][0]["quantity"] == 4
