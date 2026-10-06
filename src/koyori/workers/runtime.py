"""Runtime wiring; workers never need the identity signing private key."""

from koyori.config import Settings
from koyori.domain import Domain
from koyori.security import Cursors
from koyori.store import DynamoStore
from koyori.workers.engine import Engine


def engine() -> Engine:
    settings = Settings.from_env()
    store = DynamoStore(settings)
    fence = store.get("Sessions", ("RESTORE_FENCE", "META"))
    if fence and fence.get("blocked"):
        from koyori.errors import Problem

        raise Problem(503, "RESTORE_OFFLINE", "Restored namespace awaits operator reconciliation.")
    # Workers do not issue HTTP cursors; avoid a Secrets Manager permission here.
    return Engine(Domain(store, settings, Cursors(b"unused-worker-cursor-key" * 2)))
