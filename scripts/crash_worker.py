"""Qualification-only worker: persist one checkpoint, then wait to be killed."""

import sys
import time

from koyori.workers.runtime import engine

worker = engine()
h, tid = sys.argv[1:3]
event = next(
    x["envelope"]
    for x in worker.pending("OUTBOX")
    if x["envelope"]["aggregateId"] == tid and x["envelope"]["wake"]
)
worker.consume(event)
snapshot = worker.acquire(h, tid)
checkpoint = worker.advance(snapshot)
if checkpoint["checkpoint"] != 1:
    raise RuntimeError("Qualification checkpoint did not commit")
print("CHECKPOINT_COMMITTED", flush=True)
time.sleep(300)
