"""AWS delivery adapters with partial failures; no receipt is acknowledged early."""

import json

from boto3.dynamodb.types import TypeDeserializer

from koyori.workers.engine import Publisher
from koyori.workers.runtime import engine


def publish(event, context):
    worker = engine()
    publisher = Publisher(worker)
    failures = []
    deserialize = TypeDeserializer()
    for record in event.get("Records", []):
        try:
            image = record.get("dynamodb", {}).get("NewImage", {})
            item = {k: deserialize.deserialize(v) for k, v in image.items()}
            if str(item.get("PK", "")).startswith("OUTBOX#") and item.get("status") == "PENDING":
                publisher.publish_one(item)
        except Exception:
            failures.append({"itemIdentifier": record["dynamodb"]["SequenceNumber"]})
    return {"batchItemFailures": failures}


def _batch(event, *, activity=False):
    worker, failures = engine(), []
    for record in event.get("Records", []):
        try:
            body = json.loads(record["body"])
            # EventBridge wraps the immutable domain envelope under detail.
            raw = body.get("detail", body)
            if activity:
                worker.project_activity(raw)
            else:
                worker.consume(raw)
                from koyori.goals import Goals

                Goals(worker.domain).consume(raw)
                if raw.get("wake"):
                    worker.run(raw["householdId"], raw["aggregateId"])
        except Exception:
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}


def consume(event, context):
    return _batch(event)


def project_activity(event, context):
    return _batch(event, activity=True)


def dispatch(event, context):
    worker = engine()
    worker.run(event["householdId"], event["taskId"])
    return {"status": "RECONCILED"}


def reconcile(event, context):
    return dispatch(event, context)


def repair(event, context):
    worker = engine()
    return {"outbox": Publisher(worker).sweep(), "runs": worker.repair()}
