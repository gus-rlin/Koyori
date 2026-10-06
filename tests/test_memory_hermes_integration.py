"""Actual Dynamo transactions, index purge, leases and pre-erasure snapshot recovery."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

import pytest
from stage2_helpers import commerce
from stage3_helpers import goals, progress, submit
from test_auto_learning import FixtureReview, enabled, job, jobs, proposals
from test_memory_hermes import index, save, search

from koyori.auto_learning import AutoLearning
from koyori.backup import erasure_ledger, export_local, restore_local
from koyori.domain import Domain, hkey
from koyori.errors import Conflict, Problem
from koyori.learning import Learning
from koyori.memory import Memory
from koyori.privacy import Privacy
from koyori.security import Cursors
from koyori.store import DynamoStore, put, remove, revised

pytest_plugins = ["test_integration"]
pytestmark = pytest.mark.integration


def test_real_lexical_transactions_purge_and_cursor_have_no_loss(dynamo):
    h = dynamo
    old = save(h, text="Crème de café", visibility="household")
    expected = [old]
    for i in range(9):
        expected.append(
            save(
                h,
                text="Café chocolat",
                visibility="private" if i % 2 else "household",
                occurredAt=h.clock() - 10 + i,
            )
        )
    index(h)
    ids, cursor = [], None
    for _ in range(8):
        result = search(h, query="cafe", limit=2, cursor=cursor)
        ids += [i["id"] for i in result["items"]]
        cursor = result["nextCursor"]
        if not cursor:
            break
    assert len(ids) == len(set(ids)) == len(expected)
    ctx = h.domain.context("alex", h.h)
    _, changes, _ = Memory(h.domain).change(
        ctx, old["id"], {"text": "Crème de vanille"}, old["rev"]
    )
    h.domain.store.transact(ctx.guards() + changes)
    index(h)
    assert all(i["id"] != old["id"] for i in search(h, query="cafe")["items"])
    assert search(h, query="vanille")["items"][0]["id"] == old["id"]
    current = Memory(h.domain).get(ctx, old["id"])
    with pytest.raises(Conflict):
        h.domain.store.transact([remove("Domain", old)])
    assert Memory(h.domain).get(ctx, old["id"])["rev"] == current["rev"]


def test_real_concurrent_learning_lease_and_three_proposals(dynamo):
    h = dynamo
    service = enabled(h)
    save(h, text="Je préfère les repas simples")
    original = jobs(h)[0]
    fixture = FixtureReview(
        [dict(kind="preference", key=f"pref{i}", text=f"Préférence {i}") for i in range(3)]
    )

    def run():
        try:
            service.run(original, fixture)
        except Conflict:
            pass

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: run(), range(2)))
    assert fixture.calls == 1 and len(proposals(h)) == 3
    assert job(h, original)["sdkCalls"] == 1 and job(h, original)["status"] == "DONE"


def test_real_restore_old_snapshot_rebuilds_survivors_without_learning_succeeded_goal(
    dynamo, tmp_path
):
    h = dynamo
    commerce(h)
    service = enabled(h)
    survivor = save(h, actor="sam", text="Crème partagée survivante", visibility="household")
    private = save(h, text="Je préfère des repas simples")
    memory_job = next(j for j in jobs(h) if j["source"]["id"] == private["id"])
    service.run(memory_job, FixtureReview())
    p = proposals(h)[0]
    tid = submit(h)
    assert progress(h, tid, goals(h))["status"] == "SUCCEEDED"
    assert any(j["source"] == {"kind": "task", "id": tid} for j in jobs(h))
    index(h)
    snapshot = tmp_path / "before-erasure-v1.json"
    export_local(h.domain.store, snapshot)
    assert h.domain.store.get("Domain", (hkey(h.h), "PRIVACY#alex")) is None
    ctx = h.domain.context("alex", h.h)
    result, writes, _ = Privacy(h.domain).start(ctx)
    h.domain.store.transact(ctx.guards() + writes)
    for _ in range(10):
        Privacy(h.domain).sweep()
    assert Privacy(h.domain).get(ctx, result["id"])["status"] == "COMPLETED"
    overlay = erasure_ledger(h.domain.store)
    assert overlay["schemaVersion"] == "2.0"
    target_settings = replace(
        h.settings, prefix=f"KoyoriRestore{uuid4().hex}", learning_mode="simulated"
    )
    target = DynamoStore(target_settings)
    try:
        restored = restore_local(target, snapshot, erasure_overlay=overlay)
        assert restored["lexicalRebuild"]["households"] == 2
        domain = Domain(
            target, target_settings, Cursors(target_settings.cursor_secret(), h.clock), h.clock
        )
        assert target.get("Domain", (hkey(h.h), "PRIVACY#alex"))["epoch"] == 1
        assert target.get("Domain", (hkey(h.h), f"LEARNING#{p['id']}"))["text"] == ""
        assert target.get("Domain", (hkey(h.h), f"TASK#{tid}"))["status"] == "SUCCEEDED"
        assert list(AutoLearning(domain).pending("LEARNRUN")) == []
        AutoLearning(domain).sweep()
        fence = target.get("Sessions", ("RESTORE_FENCE", "META"))
        assert fence["blocked"]
        assert target.get("Domain", (hkey(h.h), "LEXSTATE"))["pending"] == 0
        with pytest.raises(Problem) as error:
            Learning(domain).public(domain.context("alex", h.h), p["id"])
        assert error.value.status == 404
        # Local-only operator release after reconstruction; no provider reconciliation is simulated as real.
        target.transact([put("Sessions", revised(fence, blocked=False), fence)])
        h.domain = domain
        result = search(h, query="creme")
        assert [i["id"] for i in result["items"]] == [survivor["id"]]
        assert result["indexIncomplete"] is False and search(h, query="repas")["items"] == []
        assert list(AutoLearning(domain).pending("LEARNRUN")) == []
    finally:
        for table in ("Domain", "Delivery", "Sessions", "Connections"):
            target.client.delete_table(TableName=target.name(table))
