"""Separate local queue consumers and recovery loops, all bounded per iteration."""

import argparse
import json
import logging
import time

from koyori.workers.engine import Publisher
from koyori.workers.runtime import engine


def tick(worker, role: str) -> int:
    if role == "learning":
        from koyori.auto_learning import AutoLearning

        return AutoLearning(worker.domain).sweep()
    if role == "channels":
        from koyori.privacy import Privacy
        from koyori.realtime import Signals

        Privacy(worker.domain).sweep()
        Signals(worker.domain).sweep()
        return 0
    if role in {"coordinator", "scheduler", "notifications"}:
        from koyori.workers.stage3_runtime import tick as stage3_tick

        return stage3_tick(worker.domain, role)
    if role in {"connector", "projection"}:
        from koyori.workers.stage2_runtime import tick as stage2_tick

        return stage2_tick(worker.domain, role)
    if role == "publisher":
        return Publisher(worker).sweep()
    if role == "repair":
        return worker.repair()
    sqs = worker.settings.client("sqs")
    url = worker.settings.activity_url if role == "activity" else worker.settings.workflow_url
    response = sqs.receive_message(
        QueueUrl=url, MaxNumberOfMessages=5, WaitTimeSeconds=2, VisibilityTimeout=60
    )
    for message in response.get("Messages", []):
        try:
            raw = json.loads(message["Body"])
            if role == "activity":
                worker.project_activity(raw)
            else:
                worker.consume(raw)
                from koyori.goals import Goals

                Goals(worker.domain).consume(raw)
                if raw.get("wake"):
                    worker.run(raw["householdId"], raw["aggregateId"])
            sqs.delete_message(QueueUrl=url, ReceiptHandle=message["ReceiptHandle"])
        except Exception as exc:
            logging.getLogger("koyori.worker").warning(
                json.dumps(
                    {"event": "message_retry", "role": role, "errorClass": type(exc).__name__}
                )
            )
    return len(response.get("Messages", []))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "role",
        choices=[
            "publisher",
            "workflow",
            "activity",
            "repair",
            "connector",
            "projection",
            "coordinator",
            "scheduler",
            "notifications",
            "channels",
            "learning",
        ],
    )
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    worker = engine()
    while True:
        try:
            tick(worker, args.role)
        except Exception as exc:
            logging.getLogger("koyori.worker").error(
                json.dumps(
                    {
                        "event": "iteration_retry",
                        "role": args.role,
                        "errorClass": type(exc).__name__,
                    }
                )
            )
            if args.once:
                raise
        if args.once:
            return
        time.sleep(1)


if __name__ == "__main__":
    main()
