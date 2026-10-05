"""Qualification-only process: commit a plan and remain alive until forcibly stopped."""

import sys
import time

from koyori.domain import hkey
from koyori.goals import Goals
from koyori.workers.runtime import engine

domain = engine().domain
h, tid = sys.argv[1:3]
Goals(domain).run(h, tid)
task = domain.store.get("Domain", (hkey(h), f"TASK#{tid}"))
if task["planRevision"] != 1 or task["status"] != "READY" or task["modelCalls"] != 1:
    raise RuntimeError("Qualification plan did not commit")
print("PLAN_COMMITTED", flush=True)
time.sleep(300)
