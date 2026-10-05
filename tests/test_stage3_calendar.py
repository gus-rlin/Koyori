import pytest
from stage2_helpers import commerce
from stage3_helpers import goals, progress, submit, task
from test_stage2_calendar import connect
from test_stage3_recovery import ready_action

from koyori.actions import Actions
from koyori.domain import hkey
from koyori.errors import Problem
from koyori.goals import calendar_snapshot

pytest_plugins = ["test_stage2_calendar"]


def test_calendar_material_change_blocks_old_send_then_replans_without_connection_revision_change(
    calendar,
):
    h, reader = calendar
    connection, _ = connect(h, reader)
    cid = connection["id"]
    reader.sync(h.domain.context("alex", h.h), cid)
    commerce(h)
    service = goals(h)
    service.calendar = reader
    tid = submit(h)
    aid = ready_action(h, service, tid)
    before = reader.get(h.domain.context("alex", h.h), cid)["rev"]
    reader.google.pages.append(
        {
            "items": [
                {
                    "id": "event-one",
                    "summary": "Dinner at a different time",
                    "etag": "v2",
                    "start": {"date": "2026-10-07"},
                }
            ],
            "nextSyncToken": "sync-2",
        }
    )
    reader.sync(h.domain.context("alex", h.h), cid)
    assert reader.get(h.domain.context("alex", h.h), cid)["rev"] == before
    assert h.domain.store.get("Domain", (hkey(h.h), f"CALVERSION#{cid}"))["rev"] == 2
    Actions(h.domain).run(h.h, aid)
    assert (
        Actions(h.domain).get(h.domain.context("alex", h.h), "ACTION", aid)["status"] == "BLOCKED"
    )
    event = next(
        e["envelope"]
        for e in h.engine.pending("OUTBOX")
        if e["envelope"]["type"] == "koyori.calendar.changed.v1"
        and e["envelope"]["aggregateVersion"] == 2
    )
    service.consume(event)
    assert task(h, tid)["plan"] is None
    assert progress(h, tid, service)["status"] == "SUCCEEDED"


def test_noop_calendar_sync_does_not_invalidate_a_waiting_plan(calendar):
    h, reader = calendar
    connection, _ = connect(h, reader)
    cid = connection["id"]
    reader.sync(h.domain.context("alex", h.h), cid)
    commerce(h)
    service = goals(h)
    service.calendar = reader
    tid = submit(h)
    for _ in range(3):
        service.sweep()
    assert task(h, tid)["status"] == "WAITING_TIME"
    reader.google.pages.append({"items": [], "nextSyncToken": "sync-2"})
    reader.sync(h.domain.context("alex", h.h), cid)
    assert h.domain.store.get("Domain", (hkey(h.h), f"CALVERSION#{cid}"))["rev"] == 1
    for event in h.engine.pending("OUTBOX"):
        service.consume(event["envelope"])
    service.sweep()
    assert task(h, tid)["modelCalls"] == 1


def test_partial_sync_is_not_presented_as_an_empty_complete_calendar(calendar):
    h, reader = calendar
    connection, _ = connect(h, reader)
    reader.google.pages[0]["nextPageToken"] = "page-2"
    reader.sync(h.domain.context("alex", h.h), connection["id"])
    with pytest.raises(Problem, match="CALENDAR_NOT_SYNCHRONIZED"):
        calendar_snapshot(reader, h.domain.context("alex", h.h), connection["id"])
