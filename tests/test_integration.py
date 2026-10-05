"""Same domain and API against DynamoDB Local, plus actual ElasticMQ delivery."""

import json
import os
from dataclasses import replace
from uuid import uuid4

import pytest
from conftest import Clock, Harness

from koyori.backup import export_local, restore_local
from koyori.config import Settings
from koyori.contracts import MemberCreate
from koyori.demo import initialize_keys
from koyori.domain import Domain, hkey
from koyori.errors import Conflict
from koyori.security import Cursors
from koyori.store import DynamoStore, put, revised
from koyori.workers.engine import Engine, Publisher

pytestmark = pytest.mark.integration


@pytest.fixture
def dynamo(tmp_path, monkeypatch):
    if os.getenv("KOYORI_INTEGRATION") != "1":
        pytest.skip("Set KOYORI_INTEGRATION=1 after starting local DynamoDB and ElasticMQ")
    monkeypatch.setenv("KOYORI_ISSUER_DIR", str(tmp_path / "issuer"))
    settings = replace(
        Settings(), prefix=f"KoyoriTest{uuid4().hex}", key_dir=str(tmp_path / "keys")
    )
    provider_key = tmp_path / "provider.key"
    provider_key.write_bytes(b"k" * 32)
    settings = replace(settings, token_key_file=str(provider_key))
    initialize_keys(settings)
    store = DynamoStore(settings)
    store.create_tables()
    h = Harness(settings, store, Clock())
    yield h
    for table in ("Domain", "Delivery", "Sessions", "Connections"):
        store.client.delete_table(TableName=store.name(table))


def test_real_transactions_idempotence_isolation_and_recovery(dynamo):
    h = dynamo
    key = uuid4().hex
    tid = h.command(key=key)
    assert h.command(key=key) == tid
    assert h.client.get(f"/v1/tasks/{tid}", headers=h.headers("sam")).status_code == 404
    snapshot = h.start(tid)
    assert snapshot
    checkpoint = h.engine.advance(snapshot)
    h.clock.advance(31)
    assert h.engine.advance(checkpoint) is None
    h.engine.repair()
    assert h.task(tid)["status"] == "SUCCEEDED"
    assert h.domain.context("alex", h.h).household["activeTasks"] == 0


def test_real_transaction_rolls_back_every_record(dynamo):
    from koyori.domain import row
    from koyori.errors import Conflict

    h = dynamo
    household = h.domain.context("alex", h.h).household
    with pytest.raises(Conflict):
        h.domain.store.transact(
            [
                put("Domain", row(hkey(h.h), "TEST#atomic")),
                put(
                    "Domain",
                    revised(household, activeTasks=100),
                    {**household, "rev": household["rev"] + 1},
                ),
            ]
        )
    assert h.domain.store.get("Domain", (hkey(h.h), "TEST#atomic")) is None
    assert h.domain.context("alex", h.h).household["activeTasks"] == 0


def test_membership_slot_release_is_atomic_and_idempotent(dynamo):
    h = dynamo
    ctx = h.domain.context("alex", h.h)
    _, revoke, _ = h.domain.change_member(ctx, "sam", {}, 1, revoke=True)
    other = h.domain.context("robin", h.h2)
    _, addition, _ = h.domain.add_member(other, MemberCreate(principalId="sam").model_dump())
    h.domain.store.transact(other.guards() + addition)
    with pytest.raises(Conflict):
        h.domain.store.transact(ctx.guards() + revoke)
    assert h.domain.context("sam", h.h).profile["householdCount"] == 2
    assert h.domain.store.get("Domain", ("P#sam", f"H#{h.h}")).get("active", True)
    headers = h.headers(version=1)
    path = f"/v1/households/{h.h}/members/sam"
    first = h.client.delete(path, headers=headers)
    replay = h.client.delete(path, headers=headers)
    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    assert h.domain.context("sam", h.h2).profile["householdCount"] == 1
    assert h.domain.store.get("Domain", ("P#sam", f"H#{h.h}"))["active"] is False
    assert (
        h.client.get(f"/v1/households/{h.h}/members", headers=h.headers("sam")).status_code == 403
    )


@pytest.mark.parametrize("principal", ["replacement", "sam"])
def test_expired_membership_slots_are_reconciled_atomically(dynamo, principal):
    h = dynamo
    h.clock.advance(-10)
    expires = h.clock() + 10
    expired = ["sam", "speaker", *[f"temporary{i}" for i in range(5)]]
    for pid in expired:
        ctx = h.domain.context("alex", h.h)
        if pid in {"sam", "speaker"}:
            _, writes, _ = h.domain.change_member(ctx, pid, {"expiresAt": expires}, 1, revoke=False)
        else:
            _, writes, _ = h.domain.add_member(
                ctx, MemberCreate(principalId=pid, expiresAt=expires).model_dump()
            )
        h.domain.store.transact(ctx.guards() + writes)
    h.clock.advance(10)
    body = MemberCreate(principalId=principal).model_dump()
    ctx = h.domain.context("alex", h.h)
    _, admission, _ = h.domain.add_member(ctx, body)
    other = h.domain.context("robin", h.h2)
    _, addition, _ = h.domain.add_member(other, MemberCreate(principalId="temporary0").model_dump())
    h.domain.store.transact(other.guards() + addition)
    with pytest.raises(Conflict):
        h.domain.store.transact(ctx.guards() + admission)
    assert h.domain.context("alex", h.h).household["memberCount"] == 8
    assert h.domain.store.get("Domain", (hkey(h.h), "MEMBER#sam"))["active"]
    path = f"/v1/households/{h.h}/members"
    rejected = h.client.post(path, json=body, headers=h.headers())
    assert rejected.status_code == 403 and rejected.json()["code"] == "STEP_UP_REQUIRED"
    assert h.domain.context("alex", h.h).household["memberCount"] == 8
    grant = h.grant(f"POST {path}", body)
    headers = h.headers(grant=grant)
    first = h.client.post(path, json=body, headers=headers)
    replay = h.client.post(path, json=body, headers=headers)
    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    household = h.domain.context("alex", h.h).household
    assert household["memberCount"] == 2 and household["memberIds"] == ["alex", principal]
    for pid in expired:
        member = h.domain.store.get("Domain", (hkey(h.h), f"MEMBER#{pid}"))
        profile = h.domain.store.get("Domain", (f"P#{pid}", "PROFILE"))
        link = h.domain.store.get("Domain", (f"P#{pid}", f"H#{h.h}"))
        assert member["active"] == (pid == principal)
        assert link.get("active", True) == (pid == principal)
        assert profile["householdCount"] == int(pid == principal) + int(pid == "temporary0")
    if principal == "sam":
        assert first.json()["accessEpoch"] == 2


def test_real_queues_duplicate_after_publish_crash_and_partial_batch(dynamo):
    h = dynamo
    sqs = h.settings.client("sqs")
    workflow = sqs.create_queue(QueueName=f"test-w-{uuid4().hex}")["QueueUrl"].replace(
        "elasticmq", "127.0.0.1"
    )
    activity = sqs.create_queue(QueueName=f"test-a-{uuid4().hex}")["QueueUrl"].replace(
        "elasticmq", "127.0.0.1"
    )
    settings = replace(h.settings, workflow_url=workflow, activity_url=activity)
    h.engine.settings = settings
    publisher = Publisher(h.engine)
    tid = h.command()
    event = next(x for x in h.engine.pending("OUTBOX") if x["envelope"]["aggregateId"] == tid)
    try:
        with pytest.raises(RuntimeError, match="Injected crash"):
            publisher.publish_one(event, fail_after_send=True)
        publisher.publish_one(event)
        received = sqs.receive_message(QueueUrl=workflow, MaxNumberOfMessages=10)["Messages"]
        assert len(received) == 2
        for message in received:
            h.engine.consume(json.loads(message["Body"]))
            sqs.delete_message(QueueUrl=workflow, ReceiptHandle=message["ReceiptHandle"])
        h.engine.repair()
        assert h.task(tid)["wakeSeq"] == 1
        assert h.task(tid)["status"] == "SUCCEEDED"
        received = sqs.receive_message(QueueUrl=activity, MaxNumberOfMessages=10)["Messages"]
        for message in received:
            h.engine.project_activity(json.loads(message["Body"]))
        assert len(h.client.get("/v1/activity", headers=h.headers()).json()["items"]) == 1
    finally:
        sqs.delete_queue(QueueUrl=workflow)
        sqs.delete_queue(QueueUrl=activity)


@pytest.mark.parametrize("delivery", ["lost", "late"])
def test_real_queue_loss_or_late_first_delivery_recovers_canonical_task(dynamo, delivery):
    h = dynamo
    sqs = h.settings.client("sqs")
    urls = [
        sqs.create_queue(QueueName=f"test-recovery-{kind}-{uuid4().hex}")["QueueUrl"].replace(
            "elasticmq", "127.0.0.1"
        )
        for kind in ("workflow", "activity")
    ]
    h.engine.settings = replace(h.settings, workflow_url=urls[0], activity_url=urls[1])
    try:
        tid = h.command()
        event = next(x for x in h.engine.pending("OUTBOX") if x["envelope"]["aggregateId"] == tid)
        Publisher(h.engine).publish_one(event)
        assert h.domain.store.get("Delivery", (event["PK"], event["SK"]))["status"] == "SENT"
        if delivery == "lost":
            sqs.purge_queue(QueueUrl=urls[0])
            assert not sqs.receive_message(QueueUrl=urls[0]).get("Messages")
        else:
            # The first delivery is older than the supported replay window.
            h.clock.advance(15 * 86400)
            message = sqs.receive_message(QueueUrl=urls[0])["Messages"][0]
            h.engine.consume(json.loads(message["Body"]))
            sqs.delete_message(QueueUrl=urls[0], ReceiptHandle=message["ReceiptHandle"])
        assert h.engine.repair() == 1
        task = h.domain.store.get("Domain", (hkey(h.h), f"TASK#{tid}"))
        assert task["status"] == "SUCCEEDED" and task["wakeSeq"] == 0
        assert h.domain.context("alex", h.h).household["activeTasks"] == 0
        assert h.engine.repair() == 0
    finally:
        for url in urls:
            sqs.delete_queue(QueueUrl=url)


def test_offline_restore_retrieves_rights_and_pending_work(dynamo, tmp_path):
    h = dynamo
    tid = h.command()
    snapshot = h.start(tid)
    h.engine.advance(snapshot)
    path = tmp_path / "snapshot.json"
    exported = export_local(h.domain.store, path)
    target = DynamoStore(replace(h.settings, prefix=f"KoyoriRestore{uuid4().hex}"))
    try:
        restored = restore_local(target, path)
        assert restored == exported
        domain = Domain(target, h.settings, Cursors(h.settings.cursor_secret(), h.clock), h.clock)
        assert domain.context("sam", h.h).member["active"]
        assert domain.task_access(domain.context("alex", h.h), tid)[0]["checkpoint"] == 1
        with pytest.raises(Exception) as failure:
            domain.task_access(domain.context("sam", h.h), tid)
        assert failure.value.status == 404
        h.clock.advance(31)
        Engine(domain).repair()
        assert domain.task_access(domain.context("alex", h.h), tid)[0]["status"] == "SUCCEEDED"
    finally:
        for table in ("Domain", "Delivery", "Sessions"):
            target.client.delete_table(TableName=target.name(table))
