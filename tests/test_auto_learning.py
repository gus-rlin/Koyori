"""Learning remains a sourced proposal under durable SDK, privacy and revision fences."""

import copy
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import boto3
import pytest
from botocore.awsrequest import AWSResponse
from stage2_helpers import commerce
from stage3_helpers import goals, progress, submit
from stage3_helpers import task as goal_task
from test_memory_hermes import index, save
from test_stage3_adapters import Raw

from koyori.actions import Actions
from koyori.auto_learning import AutoLearning, StrandsLearning
from koyori.backup import apply_suppressions, ledger_hash
from koyori.domain import hkey
from koyori.errors import Conflict
from koyori.learning import Learning
from koyori.memory import Memory
from koyori.privacy import Privacy
from koyori.stage2_contracts import ContextQuery
from koyori.stage3_contracts import LearningSubmit
from koyori.store import MemoryStore, put, remove


def enabled(h, **values):
    h.domain.settings = replace(h.domain.settings, learning_mode="simulated", **values)
    return AutoLearning(h.domain)


def proposals(h):
    return h.domain.store.query("Domain", hkey(h.h), prefix="LEARNING#", limit=100)[0]


def jobs(h):
    service = AutoLearning(h.domain)
    return list(service.pending("LEARNRUN"))


def job(h, original):
    return h.domain.store.get("Delivery", (original["PK"], original["SK"]))


class FixtureReview:
    mode = "simulated"

    def __init__(self, values=None, callback=None, fail=False):
        self.values = (
            values
            if values is not None
            else [dict(kind="preference", key="dessert", text="Moins sucré")]
        )
        self.callback, self.fail, self.calls = callback, fail, 0

    def generate(self, payload, quota):
        quota.reserve()
        self.calls += 1
        if self.callback:
            self.callback(payload)
        if self.fail:
            raise RuntimeError("synthetic failure containing private source")
        return {"proposals": self.values}


def decision(h, proposal, value="accept"):
    ctx = h.domain.context("alex", h.h)
    result, writes, _ = Learning(h.domain).decide(
        ctx, proposal["id"], {"decision": value}, proposal["rev"]
    )
    h.domain.store.transact(ctx.guards() + writes)
    return result


def test_simulated_proposal_requires_acceptance_and_does_not_loop(harness):
    h = harness
    service = enabled(h)
    source = save(h, text="Je préfère le chocolat au petit déjeuner")
    original = jobs(h)[0]
    service.run(original)
    items = proposals(h)
    assert (
        len(items) == 1
        and items[0]["source"]["kind"] == "memory"
        and items[0]["source"]["id"] == source["id"]
    )
    assert items[0]["origin"] == "automatic" and items[0]["mode"] == "simulated"
    ctx = h.domain.context("alex", h.h)
    before = Memory(h.domain).context(ctx, ContextQuery(includeCore=True).model_dump())
    assert before["coreItems"] == []
    result = decision(h, items[0])
    after = Memory(h.domain).context(
        h.domain.context("alex", h.h), ContextQuery(includeCore=True).model_dump()
    )
    assert [m["id"] for m in after["coreItems"]] == [result["memoryId"]]
    assert jobs(h) == [] and job(h, original)["sdkCalls"] == 1
    index(h)
    assert jobs(h) == []  # Acceptance and operator backfill never create learning intentions.


@pytest.mark.parametrize(
    "text", ["Du chocolat aujourd'hui", "Je préfère le chocolat ce soir", "Achat réussi : chocolat"]
)
def test_episodic_request_and_successful_purchase_are_not_preferences(harness, text):
    h = harness
    service = enabled(h)
    save(h, text=text)
    service.sweep()
    assert proposals(h) == []


def test_atomic_three_proposals_group_notifications_and_deduplicate_rejections(harness):
    h = harness
    service = enabled(h)
    save(h, text="Je préfère des repas simples et peu sucrés")
    values = [dict(kind="preference", key=f"pref{i}", text=f"Préférence {i}") for i in range(3)]
    fixture = FixtureReview(values + [])
    service.run(jobs(h)[0], fixture)
    first = proposals(h)
    assert len(first) == 3
    records = h.domain.store.query("Delivery", f"NOTIFY#{h.h}#alex", prefix="BATCH#")[0]
    assert {e["id"] for r in records for e in r["entries"]} == {p["id"] for p in first}
    for p in first:
        decision(h, p, "reject")
    save(h, text="Je préfère des repas simples et peu sucrés")
    service.run(jobs(h)[0], fixture)
    assert len(proposals(h)) == 3 and all(p["status"] == "REJECTED" for p in proposals(h))


def test_duplicate_drafts_in_one_result_publish_once(harness):
    h = harness
    service = enabled(h)
    save(h, text="Je préfère moins de sucre")
    value = dict(kind="preference", key="dessert", text="Moins sucré")
    service.run(jobs(h)[0], FixtureReview([value, value, value]))
    assert len(proposals(h)) == 1


def test_correction_preserves_existing_sharing_expiration_and_requires_target_revision(harness):
    h = harness
    target = save(
        h,
        kind="preference",
        key="dessert",
        text="Sucré",
        visibility="household",
        validUntil=h.clock() + 3600,
    )
    service = enabled(h)
    save(h, text="Je préfère désormais moins de sucre")
    service.run(jobs(h)[0], FixtureReview())
    p = proposals(h)[0]
    assert p["targetMemoryId"] == target["id"] and p["targetRevision"] == target["rev"]
    result = decision(h, p)
    actual = Memory(h.domain).get(h.domain.context("alex", h.h), result["memoryId"])
    assert actual["visibility"] == "household" and actual["validUntil"] == target["validUntil"]
    assert actual["text"] == "Moins sucré"


@pytest.mark.parametrize("mutation", ["source", "target", "delete-target", "new-target", "erase"])
def test_changes_during_model_call_never_publish_stale_proposals(harness, mutation):
    h = harness
    if mutation in {"target", "delete-target"}:
        target = save(h, kind="preference", key="dessert", text="Sucré")
    service = enabled(h)
    source = save(h, text="Je préfère moins de sucre")
    original = jobs(h)[0]

    def change(_):
        ctx = h.domain.context("alex", h.h)
        if mutation == "new-target":
            save(h, kind="preference", key="dessert", text="Créée pendant l'appel")
        elif mutation == "erase":
            _, writes, _ = Privacy(h.domain).start(ctx)
            h.domain.store.transact(ctx.guards() + writes)
        else:
            item = source if mutation == "source" else target
            _, writes, _ = Memory(h.domain).change(
                ctx,
                item["id"],
                {"text": "Correction concurrente"},
                item["rev"],
                delete=mutation == "delete-target",
            )
            h.domain.store.transact(ctx.guards() + writes)

    service.run(original, FixtureReview(callback=change))
    assert proposals(h) == []


@pytest.mark.parametrize("mutation", ["source", "target", "delete-target", "rejected-target"])
def test_proposal_read_and_export_hide_changed_source_or_target(harness, mutation):
    h = harness
    target = save(h, kind="preference", key="dessert", text="Sucré")
    source = save(h, text="Moins de sucre")
    ctx = h.domain.context("alex", h.h)
    result, writes, _ = Learning(h.domain).propose(
        ctx,
        LearningSubmit(
            kind="preference",
            key="dessert",
            text="Texte retiré",
            source={"kind": "memory", "id": source["id"]},
            targetMemoryId=target["id"],
            targetRevision=target["rev"],
        ).model_dump(),
    )
    h.domain.store.transact(ctx.guards() + writes)
    if mutation == "rejected-target":
        decision(h, proposals(h)[0], "reject")
    changed = source if mutation == "source" else target
    _, changes, _ = Memory(h.domain).change(
        ctx,
        changed["id"],
        {"text": "Source corrigée"},
        changed["rev"],
        delete=mutation in {"delete-target", "rejected-target"},
    )
    h.domain.store.transact(ctx.guards() + changes)
    assert Learning(h.domain).public(ctx, result["id"])["text"] == ""
    assert "Texte retiré" not in h.client.get("/v1/learning", headers=h.headers()).text
    cursor, exported = None, []
    while True:
        page = Privacy(h.domain).export(ctx, cursor)
        exported += page["items"]
        cursor = page["nextCursor"]
        if not cursor:
            break
    assert "Texte retiré" not in json.dumps(exported, ensure_ascii=False)


def test_default_twenty_daily_reservations_and_seven_day_eligibility(harness):
    h = harness
    service = enabled(h)
    for i in range(21):
        save(h, text=f"Je préfère des repas simples {i}")
    fixture = FixtureReview([])
    candidates = jobs(h)
    # Service.pending deliberately bounds one sweep at twenty; a second captures the rest.
    for candidate in candidates:
        service.run(candidate, fixture)
    for candidate in jobs(h):
        service.run(candidate, fixture)
    deferred = [
        v
        for (table, _), v in h.domain.store.rows.items()
        if table == "Delivery" and v["PK"].startswith("LEARNRUN#") and v["status"] == "PENDING"
    ]
    assert fixture.calls == 20 and len(deferred) == 1 and deferred[0]["sdkCalls"] == 0
    original = deferred[0]
    h.clock.advance(7 * 86400 + 1)
    service.run(original, fixture)
    assert fixture.calls == 20 and job(h, original)["status"] == "SKIPPED"


def test_daily_learning_credit_is_shared_across_a_persons_households(harness):
    from uuid import uuid4

    from koyori.contracts import HouseholdCreate

    h = harness
    service = enabled(h, learning_daily_limit=1)
    save(h, text="Je préfère moins de sucre")
    service.run(jobs(h)[0], FixtureReview([]))
    other = h.domain.create_household(
        "alex", HouseholdCreate(name="Synthetic quota household").model_dump(), uuid4().hex
    )
    h.h = other["id"]
    save(h, text="Je préfère plus de chocolat")
    original = next(j for j in jobs(h) if j["h"] == h.h)
    reviewer = FixtureReview([])
    service.run(original, reviewer)
    assert reviewer.calls == 0 and job(h, original)["sdkCalls"] == 0
    assert job(h, original)["outcome"] == "LEARNING_DAILY_LIMIT"


def test_erasure_of_two_pre_migration_memories_without_lexical_state(harness):
    h = harness
    saved = [save(h, text=f"Ancienne mémoire {i}") for i in range(2)]
    state = h.domain.store.get("Domain", (hkey(h.h), "LEXSTATE"))
    changes = [remove("Domain", state)]
    changes += [
        remove("Delivery", h.domain.store.get("Delivery", (f"LEXRUN#{m['id']}", "META")))
        for m in saved
    ]
    h.domain.store.transact(changes)
    ctx = h.domain.context("alex", h.h)
    result, writes, _ = Privacy(h.domain).start(ctx)
    h.domain.store.transact(ctx.guards() + writes)
    for _ in range(4):
        Privacy(h.domain).sweep()
    assert Privacy(h.domain).get(ctx, result["id"])["status"] == "COMPLETED"
    index(h)
    assert h.domain.store.get("Domain", (hkey(h.h), "LEXSTATE"))["pending"] == 0


def test_lifetime_requests_retry_and_daily_deferral_are_durable(harness):
    h = harness
    service = enabled(h, learning_daily_limit=1)
    save(h, text="Je préfère des repas simples")
    original = jobs(h)[0]
    fixture = FixtureReview(fail=True)
    service.run(original, fixture)
    assert job(h, original)["sdkCalls"] == 1 and job(h, original)["dueAt"] == h.clock() + 30
    h.clock.advance(30)
    service.run(original, fixture)
    assert fixture.calls == 1 and job(h, original)["outcome"] == "LEARNING_DAILY_LIMIT"
    tomorrow = (h.clock() // 86400 + 1) * 86400
    assert job(h, original)["dueAt"] == tomorrow
    h.clock.value = tomorrow
    service.run(original, fixture)
    assert fixture.calls == 2 and job(h, original)["sdkCalls"] == 2
    assert job(h, original)["status"] == "FAILED"
    service.run(original, fixture)
    assert fixture.calls == 2


def test_crash_after_sdk_reservation_and_expired_lease_preserves_request_ceiling(harness):
    h = harness
    service = enabled(h)
    save(h, text="Je préfère des repas simples")
    original = jobs(h)[0]

    class Crash(FixtureReview):
        def generate(self, payload, quota):
            quota.reserve()
            raise SystemExit("simulated worker death")

    with pytest.raises(SystemExit):
        service.run(original, Crash())
    assert job(h, original)["sdkCalls"] == 1 and job(h, original)["leaseUntil"] > h.clock()
    successor = FixtureReview()
    service.run(original, successor)
    assert successor.calls == 0
    h.clock.advance(121)
    service.run(original, successor)
    assert successor.calls == 1 and job(h, original)["sdkCalls"] == 2
    assert len(proposals(h)) == 1


def test_two_workers_publish_once(harness):
    h = harness
    service = enabled(h)
    save(h, text="Je préfère des repas simples")
    original = jobs(h)[0]
    fixture = FixtureReview()

    def run():
        try:
            service.run(original, fixture)
        except Conflict:
            pass

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: run(), range(2)))
    assert fixture.calls == 1 and len(proposals(h)) == 1 and job(h, original)["sdkCalls"] == 1


def test_goal_success_creates_intention_but_failure_and_cancel_do_not(harness):
    h = harness
    commerce(h)
    enabled(h)
    tid = submit(h)
    done = progress(h, tid, goals(h))
    assert done["status"] == "SUCCEEDED"
    candidate = next(j for j in jobs(h) if j["source"] == {"kind": "task", "id": tid})
    service = AutoLearning(h.domain)
    payload, _, _ = service.payload(h.domain.context("alex", h.h), done, candidate)
    assert payload["observedSteps"] and all(s["receipt"] for s in payload["observedSteps"])
    service.run(candidate, FixtureReview())
    assert proposals(h) == []  # A successful meal alone expresses no durable preference.
    failed = submit(h, "Une capacité inconnue")
    assert progress(h, failed, goals(h))["status"] == "NEEDS_ATTENTION"
    assert all(j["source"]["id"] != failed for j in jobs(h))


def test_memory_erasure_does_not_replace_confirmed_goal_success(harness):
    h = harness
    commerce(h)
    enabled(h)
    tid = submit(h)
    service = goals(h)
    for _ in range(40):
        service.sweep()
        Actions(h.domain).sweep()
        current = goal_task(h, tid)
        if current["stepStates"] and all(
            s["status"] == "DONE" for s in current["stepStates"].values()
        ):
            break
        h.clock.advance(5)
    assert current["status"] != "SUCCEEDED" and current["stepStates"]["dinner"]["receipt"]
    ctx = h.domain.context("alex", h.h)
    _, writes, _ = Privacy(h.domain).start(ctx)
    h.domain.store.transact(ctx.guards() + writes)
    service.sweep()
    assert goal_task(h, tid)["status"] == "SUCCEEDED"
    assert all(j["source"]["id"] != tid for j in jobs(h))


class LearningTransport:
    def __init__(self, invalid=False, throttle=False):
        self.calls, self.invalid, self.throttle = [], invalid, throttle

    def model(self, **kwargs):
        from strands.models import BedrockModel

        session = boto3.Session(
            region_name=kwargs.pop("region_name"),
            aws_access_key_id="fixture",
            aws_secret_access_key="fixture",
        )
        model = BedrockModel(boto_session=session, **kwargs)

        def send(request):
            payload = json.loads(request.body)
            self.calls.append(payload)
            logging.getLogger("strands.event_loop.streaming").warning("PRIVATE_LEARNING_FRAGMENT")
            if self.throttle:
                return AWSResponse(
                    request.url,
                    429,
                    {"x-amzn-errortype": "ThrottlingException"},
                    Raw(b'{"message":"fixture throttle"}'),
                )
            name = payload["toolConfig"]["tools"][0]["toolSpec"]["name"]
            content = {
                "proposals": [{"kind": "preference", "key": "dessert", "text": "Moins sucré"}]
            }
            if self.invalid:
                content["proposals"][0]["kind"] = "shell"
            response = {
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "toolUse": {
                                    "toolUseId": f"result-{len(self.calls)}",
                                    "name": name,
                                    "input": content,
                                }
                            }
                        ],
                    }
                },
                "stopReason": "tool_use",
                "usage": {"inputTokens": 100, "outputTokens": 50, "totalTokens": 150},
                "metrics": {"latencyMs": 1},
            }
            return AWSResponse(
                request.url,
                200,
                {"content-type": "application/json"},
                Raw(json.dumps(response).encode()),
            )

        model.client._endpoint.http_session.send = send
        return model


@pytest.mark.parametrize("invalid,throttle", [(False, False), (True, False), (False, True)])
def test_actual_sdk_transport_enforces_two_request_ceiling_including_repairs(
    harness, caplog, invalid, throttle
):
    h = harness
    service = enabled(h)
    save(h, text="Je préfère moins de sucre")
    original = jobs(h)[0]
    transport = LearningTransport(invalid, throttle)
    reviewer = StrandsLearning(h.domain.settings, transport.model)
    with caplog.at_level(logging.WARNING):
        for _ in range(4):
            service.run(original, reviewer)
            h.clock.advance(31)
    assert 1 <= len(transport.calls) <= 2 and job(h, original)["sdkCalls"] == len(transport.calls)
    assert all(
        p["inferenceConfig"]["maxTokens"] == 2048 and len(p["toolConfig"]["tools"]) == 1
        for p in transport.calls
    )
    assert "PRIVATE_LEARNING_FRAGMENT" not in caplog.text
    if not invalid and not throttle:
        assert len(proposals(h)) == 1 and proposals(h)[0]["mode"] == "real"
    else:
        assert proposals(h) == [] and job(h, original)["status"] == "FAILED"


def test_erasure_old_rows_and_restore_overlay_remove_proposals_jobs_and_preserve_fences(harness):
    h = harness
    old = save(h, text="Ancien échange avant migration")
    save(h, text="Second ancien échange")
    # Simulate a pre-migration namespace (canonical data exists, no lexical state).
    state = h.domain.store.get("Domain", (hkey(h.h), "LEXSTATE"))
    h.domain.store.transact([remove("Domain", state)])
    service = enabled(h)
    save(h, text="Je préfère moins de sucre")
    service.run(jobs(h)[0], FixtureReview())
    tables = {
        t: [copy.deepcopy(v) for (table, _), v in h.domain.store.rows.items() if table == t]
        for t in ("Domain", "Delivery", "Sessions", "Connections")
    }
    ctx = h.domain.context("alex", h.h)
    result, changes, _ = Privacy(h.domain).start(ctx)
    h.domain.store.transact(ctx.guards() + changes)
    for _ in range(10):
        Privacy(h.domain).sweep()
    assert Privacy(h.domain).get(ctx, result["id"])["status"] == "COMPLETED"
    assert all(p["deleted"] and p["text"] == "" for p in proposals(h))
    fence = h.domain.store.get("Domain", (hkey(h.h), "PRIVACY#alex"))
    entries = [
        {"PK": v["PK"], "SK": v["SK"], "revision": v["rev"]}
        for (t, _), v in h.domain.store.rows.items()
        if t == "Domain" and v.get("deleted") and v["SK"].startswith(("MEMORY#", "LEARNING#"))
    ]
    ledger = {"schemaVersion": "2.0", "entries": entries, "privacyFences": [fence]}
    ledger["sha256"] = ledger_hash(ledger)
    restored = apply_suppressions(tables, ledger)
    assert not any(
        i["PK"].startswith(("LEARNRUN#", "LEARNOWNER#", "LEXRUN#", "LEX#", "LEXDOC#"))
        for rows in restored.values()
        for i in rows
    )
    assert (
        next(i for i in restored["Domain"] if i["SK"] == "PRIVACY#alex")["epoch"] == fence["epoch"]
    )
    assert all(not p.get("text") for p in restored["Domain"] if p["SK"].startswith("LEARNING#"))
    assert old["text"] not in json.dumps(restored, ensure_ascii=False)
    restored_store = MemoryStore()
    for table, rows in restored.items():
        restored_store.transact([put(table, i) for i in rows])
    h.domain.store = restored_store
    AutoLearning(h.domain).sweep()
    assert jobs(h) == []
