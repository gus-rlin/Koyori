"""Real conditional ticket consumption and finalized turns in DynamoDB Local."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

import pytest

from koyori.errors import Problem
from koyori.sessions import Sessions
from koyori.stage4_contracts import SessionCreate
from koyori.voice import VoiceSession

pytest_plugins = ["test_integration"]
pytestmark = pytest.mark.integration


def test_dynamo_concurrent_ticket_has_exactly_one_consumer(dynamo):
    h = dynamo
    h.domain.settings = replace(h.domain.settings, speech_mode="simulated")
    service = Sessions(h.domain)
    grant = service.issue(
        h.domain.context("alex", h.h),
        SessionCreate(mode="personal", microphoneConsent=True).model_dump(),
    )

    def consume():
        try:
            return service.consume(grant["ticket"], grant["runtimeSessionId"])["state"]
        except Problem:
            return "REFUSED"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: consume(), range(2)))
    assert sorted(results) == ["ACTIVE", "REFUSED"]


def test_dynamo_final_turn_transaction_has_one_task_memory_and_quota(dynamo):
    h = dynamo
    h.domain.settings = replace(h.domain.settings, speech_mode="simulated")
    service = Sessions(h.domain)
    grant = service.issue(
        h.domain.context("alex", h.h),
        SessionCreate(mode="personal", microphoneConsent=True).model_dump(),
    )
    service.consume(grant["ticket"], grant["runtimeSessionId"])
    turn = uuid4().hex

    def finalize():
        return VoiceSession(h.domain, grant["runtimeSessionId"]).finalize(
            turn, "Prépare le dîner pour deux", submit=True
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(lambda _: finalize(), range(2)))
    assert first == second
    assert h.domain.context("alex", h.h).household["activeTasks"] == 1
    service.close(grant["runtimeSessionId"])
    assert h.task(first["taskId"])["status"] == "READY"


def test_restore_old_snapshot_waits_for_accepted_erasure_to_finish(dynamo, tmp_path):
    from koyori.backup import erasure_ledger, export_local, restore_local
    from koyori.domain import hkey
    from koyori.memory import Memory
    from koyori.privacy import Privacy
    from koyori.stage2_contracts import MemoryWrite
    from koyori.store import DynamoStore

    h = dynamo
    ctx = h.domain.context("alex", h.h)
    saved, changes, _ = Memory(h.domain).create(
        ctx, MemoryWrite(kind="exchange", text="Erase after snapshot").model_dump()
    )
    h.domain.store.transact(ctx.guards() + changes)
    snapshot = tmp_path / "before-erasure.json"
    export_local(h.domain.store, snapshot)
    _, erasing, _ = Privacy(h.domain).start(ctx)
    h.domain.store.transact(ctx.guards() + erasing)
    with pytest.raises(ValueError, match="Complete pending memory erasures"):
        erasure_ledger(h.domain.store)
    for _ in range(4):
        Privacy(h.domain).sweep()
    ledger = erasure_ledger(h.domain.store)
    target = DynamoStore(replace(h.settings, prefix=f"KoyoriRestore{uuid4().hex}"))
    try:
        restore_local(target, snapshot, erasure_overlay=ledger)
        restored = target.get("Domain", (hkey(h.h), f"MEMORY#{saved['id']}"))
        assert restored["deleted"] and restored["text"] == ""
        assert target.get("Sessions", ("RESTORE_FENCE", "META"))["blocked"]
    finally:
        for table in ("Domain", "Delivery", "Sessions", "Connections"):
            target.client.delete_table(TableName=target.name(table))
