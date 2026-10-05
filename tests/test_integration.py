"""Same domain and API against DynamoDB Local, plus actual ElasticMQ delivery."""

import json
import os
from dataclasses import replace
from uuid import uuid4

import pytest
from conftest import Clock, Harness

from koyori.backup import export_local, restore_local
from koyori.config import Settings
from koyori.demo import initialize_keys
from koyori.domain import Domain, hkey
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
    initialize_keys(settings)
    store = DynamoStore(settings)
    store.create_tables()
    h = Harness(settings, store, Clock())
    yield h
    for table in ("Domain", "Delivery", "Sessions"):
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
