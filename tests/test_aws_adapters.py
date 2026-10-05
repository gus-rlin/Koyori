import json

from koyori.workers import lambda_handlers
from koyori.workers.engine import Publisher


def test_sqs_lambda_reports_only_uncommitted_records(harness, monkeypatch):
    tid = harness.command()
    event = next(
        x["envelope"]
        for x in harness.engine.pending("OUTBOX")
        if x["envelope"]["aggregateId"] == tid
    )
    monkeypatch.setattr(lambda_handlers, "engine", lambda: harness.engine)
    batch = {
        "Records": [
            {"messageId": "valid", "body": json.dumps({"detail": event})},
            {"messageId": "invalid", "body": json.dumps({**event, "schemaVersion": "2.0"})},
        ]
    }
    result = lambda_handlers.consume(batch, None)
    assert result == {"batchItemFailures": [{"itemIdentifier": "invalid"}]}
    assert harness.task(tid)["status"] == "SUCCEEDED"
    assert lambda_handlers.consume(batch, None) == result
    assert harness.task(tid)["wakeSeq"] == 1


def test_eventbridge_per_entry_failure_does_not_mark_outbox_sent(harness):
    tid = harness.command()
    item = next(x for x in harness.engine.pending("OUTBOX") if x["envelope"]["aggregateId"] == tid)
    publisher = Publisher(harness.engine)
    publisher.sqs = None

    class Rejected:
        def put_events(self, **args):
            return {"FailedEntryCount": 1, "Entries": [{"ErrorCode": "InternalFailure"}]}

    publisher.events = Rejected()
    try:
        publisher.publish_one(item)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Failed EventBridge entry must fail publication")
    current = harness.domain.store.get("Delivery", (item["PK"], item["SK"]))
    assert current["status"] == "PENDING" and "ttl" not in current
