"""Observable core/archive behavior, canonical index repair and bounded disclosure."""

import hashlib
import json
from datetime import UTC, datetime

import pytest
from stage3_helpers import goals, task

from koyori.domain import row
from koyori.errors import Conflict, Problem
from koyori.lexical import Lexical, posting_pk, scope
from koyori.memory import Memory
from koyori.stage2_contracts import ContextQuery, MemorySearch, MemoryWrite
from koyori.store import put, remove, revised


def save(h, *, actor="alex", kind="exchange", text="Archive synthétique", **values):
    ctx = h.domain.context(actor, h.h)
    result, writes, _ = Memory(h.domain).create(
        ctx, MemoryWrite(kind=kind, text=text, **values).model_dump()
    )
    h.domain.store.transact(ctx.guards() + writes)
    return Memory(h.domain).get(ctx, result["id"])


def index(h):
    service = Lexical(h.domain)
    while service.backfill(h.h, drain=True)["more"]:
        pass
    return service


def search(h, *, actor="alex", **body):
    return Lexical(h.domain).search(h.domain.context(actor, h.h), MemorySearch(**body).model_dump())


def keyed_goal(h, text, keys):
    response = h.client.post(
        "/v1/goals", json={"text": text, "memoryKeys": keys}, headers=h.headers()
    )
    assert response.status_code == 202, response.text
    return response.json()["id"]


def test_core_survives_500_newer_exchanges_without_violating_civil_day(harness):
    h = harness
    old = save(
        h,
        kind="preference",
        key="breakfast_drink",
        text="Je préfère le chocolat",
        occurredAt=h.clock() - 86400 * 30,
    )
    for i in range(505):
        save(h, text=f"Échange récent {i}", occurredAt=h.clock() - 1)
    ctx = h.domain.context("alex", h.h)
    default = Memory(h.domain).context(ctx, ContextQuery(day="yesterday").model_dump())
    assert default["items"] == default["coreItems"] == []
    result = Memory(h.domain).context(
        ctx, ContextQuery(day="yesterday", includeCore=True).model_dump()
    )
    assert result["items"] == [] and [i["id"] for i in result["coreItems"]] == [old["id"]]
    tid = keyed_goal(h, "Prépare le petit déjeuner", ["breakfast_drink"])
    ctx = h.domain.context("alex", h.h)
    payload = goals(h).context_payload(ctx, task(h, tid))
    assert payload["memories"][0]["id"] == old["id"] and payload["missingMemoryKeys"] == []


def test_old_archive_search_normalizes_unicode_accents_case_and_intersects_terms(harness):
    h = harness
    old = save(h, text="Une crème CAFÉ délicieuse", occurredAt=h.clock() - 10000)
    save(h, text="Le café sans dessert")
    for i in range(501):
        save(h, text=f"Autre souvenir {i}")
    index(h)
    response = h.client.post(
        "/v1/memories/search", json={"query": "CRÈME cafe"}, headers=h.headers()
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert [i["id"] for i in result["items"]] == [old["id"]]
    assert result["nextCursor"] is None and result["indexIncomplete"] is False
    context = h.client.post("/v1/context", json={"query": "creme cafe"}, headers=h.headers()).json()
    assert [i["id"] for i in context["items"]] == [old["id"]]
    assert context["truncated"]  # The recent archive scan still hit its bounded window.
    assert (
        h.client.post(
            "/v1/memories/search", json={"query": "je le"}, headers=h.headers()
        ).status_code
        == 422
    )
    assert (
        h.client.post(
            "/v1/memories/search", json={"query": "aa bb cc dd ee ff gg hh ii"}, headers=h.headers()
        ).status_code
        == 422
    )


def test_cursor_advances_consumed_private_and_shared_positions_only(harness):
    h = harness
    expected = []
    for i in range(14):
        expected.append(
            save(
                h,
                visibility="household" if i % 2 else "private",
                text=f"Chocolat souvenir {i}",
                occurredAt=h.clock() - 100 + i,
            )
        )
    foreign = save(h, actor="sam", text="Chocolat privé Sam")
    index(h)
    ids, cursor = [], None
    for _ in range(20):
        result = search(h, query="chocolat", limit=3, cursor=cursor, maxCharacters=1400)
        ids += [i["id"] for i in result["items"]]
        cursor = result["nextCursor"]
        if not cursor:
            break
    assert ids == [i["id"] for i in reversed(expected)] and foreign["id"] not in ids
    first = search(h, query="chocolat", limit=1)
    for actor, query in (("sam", "chocolat"), ("alex", "souvenir")):
        with pytest.raises(Problem) as error:
            search(h, actor=actor, query=query, limit=1, cursor=first["nextCursor"])
        assert error.value.status == 400
    shared = search(h, actor="speaker", query="chocolat")
    assert {i["id"] for i in shared["items"]} == {
        i["id"] for i in expected if i["visibility"] == "household"
    }


def test_empty_filtered_page_with_cursor_is_not_absence(harness):
    h = harness
    wanted = save(
        h, kind="preference", key="dessert", text="Chocolat durable", occurredAt=h.clock() - 10000
    )
    for i in range(502):
        save(h, text=f"Chocolat épisode {i}", occurredAt=h.clock() - i)
    index(h)
    first = search(h, query="chocolat", kinds=["preference"])
    assert first["items"] == [] and first["nextCursor"] and first["truncated"]
    second = search(h, query="chocolat", kinds=["preference"], cursor=first["nextCursor"])
    assert [i["id"] for i in second["items"]] == [wanted["id"]] and second["nextCursor"] is None


def test_search_filters_civil_day_during_dst_and_kind(harness):
    h = harness
    h.clock.value = int(datetime(2026, 10, 27, tzinfo=UTC).timestamp())
    left = int(datetime(2026, 10, 24, 22, tzinfo=UTC).timestamp())
    right = int(datetime(2026, 10, 25, 23, tzinfo=UTC).timestamp())
    included = [
        save(h, text="Crème dessert", occurredAt=left),
        save(h, text="Crème dessert", occurredAt=right - 1),
    ]
    save(h, text="Crème dessert", occurredAt=left - 1)
    save(h, text="Crème dessert", occurredAt=right)
    index(h)
    result = search(h, query="creme", day="2026-10-25", kinds=["exchange"])
    assert result["range"] == {"start": left, "end": right} and right - left == 25 * 3600
    assert {i["id"] for i in result["items"]} == {i["id"] for i in included}


def test_projection_resume_replaces_stale_terms_and_never_calls_semantic_model(harness):
    h = harness
    old = save(h, text=" ".join(f"terme{i}" for i in range(95)))
    service = Lexical(h.domain)
    intent = h.domain.store.get("Delivery", (f"LEXRUN#{old['id']}", "META"))
    service.project(intent)  # Empty purge -> build, then one partial batch.
    service.project(intent)
    assert h.domain.store.get("Delivery", (intent["PK"], "META"))["position"] == 32
    ctx = h.domain.context("alex", h.h)
    _, changes, _ = Memory(h.domain).change(ctx, old["id"], {"text": "Crème révisée"}, old["rev"])
    h.domain.store.transact(ctx.guards() + changes)
    index(h)
    assert search(h, query="terme1")["items"] == []
    assert search(h, query="creme")["items"][0]["rev"] == 2
    term = hashlib.sha256(b"terme1").hexdigest()
    assert h.domain.store.query("Domain", posting_pk(scope(h.h, "alex", "private"), term))[0] == []
    current = Memory(h.domain).get(ctx, old["id"])
    _, changes, _ = Memory(h.domain).change(ctx, old["id"], {}, current["rev"], delete=True)
    h.domain.store.transact(ctx.guards() + changes)
    assert search(h, query="creme")["items"] == []  # Canonical reread precedes async purge.
    index(h)
    assert h.domain.store.query("Domain", f"LEXDOC#{h.h}#{old['id']}")[0] == []


def test_core_only_playback_guard_and_multibyte_planning_budgets(harness):
    h = harness
    for i in range(10):
        save(h, kind="preference", key=f"pref{i}", text="茶" * 600)
    ctx = h.domain.context("alex", h.h)
    tid = keyed_goal(h, "Consulte mes préférences", ["pref0"])
    ctx = h.domain.context("alex", h.h)
    payload = goals(h).context_payload(ctx, task(h, tid))
    assert payload["memories"][0]["key"] == "pref0"
    assert len(payload["memories"]) <= 14
    assert sum(len(json.dumps(i, ensure_ascii=False)) for i in payload["memories"]) <= 8000
    assert len(json.dumps(payload, ensure_ascii=False).encode()) <= 20000
    from koyori.channel_tools import ChannelTools
    from koyori.privacy import Privacy

    result = Memory(h.domain).context(
        ctx, ContextQuery(day="yesterday", includeCore=True).model_dump()
    )
    assert result["items"] == [] and result["coreItems"]
    checks = ChannelTools(h.domain).result_checks(ctx, result)
    _, erasing, _ = Privacy(h.domain).start(ctx)
    h.domain.store.transact(ctx.guards() + erasing)
    with pytest.raises(Conflict):
        h.domain.store.transact(ctx.guards() + checks)


def test_planner_byte_bound_includes_keys_missing_after_trimming(harness):
    h = harness
    keys = [f"pref{i}_" + "k" * 58 for i in range(8)]
    for key in keys:
        save(h, kind="preference", key=key, text="😀" * 450)
    tid = keyed_goal(h, "a", keys)
    ctx = h.domain.context("alex", h.h)
    service = goals(h)
    current = task(h, tid)
    baseline = service.context_payload(ctx, current)
    assert len(baseline["memories"]) == 8 and baseline["missingMemoryKeys"] == []
    # Set a valid multibyte goal so one removal reaches 19999 bytes without
    # its newly missing key. That key must participate in the next bound check.
    baseline["goal"] = ""
    baseline["contextTruncated"] = True
    baseline["memories"].pop()
    goal_bytes = 19999 - len(json.dumps(baseline, ensure_ascii=False).encode())
    large_goal = "😀" * (goal_bytes // 4) + "a" * (goal_bytes % 4)
    assert 0 < len(large_goal) <= 2000
    payload = service.context_payload(ctx, {**current, "goal": large_goal})
    assert len(json.dumps(payload, ensure_ascii=False).encode()) <= 20000
    assert len(payload["memories"]) == 6 and len(payload["missingMemoryKeys"]) == 2
    assert set(payload["missingMemoryKeys"]) == set(keys) - {m["key"] for m in payload["memories"]}


def test_conditional_delete_loses_to_revision_change_and_is_atomic(harness):
    store = harness.domain.store
    old = row("DERIVED", "posting")
    store.transact([put("Domain", old)])
    store.transact([put("Domain", revised(old, value=2), old)])
    with pytest.raises(Conflict):
        store.transact([remove("Domain", old), put("Domain", row("DERIVED", "uncommitted"))])
    assert store.get("Domain", ("DERIVED", "posting"))["value"] == 2
    assert store.get("Domain", ("DERIVED", "uncommitted")) is None
