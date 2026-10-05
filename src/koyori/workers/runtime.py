"""Runtime wiring; workers never need the identity signing private key."""

from koyori.config import Settings
from koyori.domain import Domain
from koyori.security import Cursors
from koyori.store import DynamoStore
from koyori.workers.engine import Engine


def engine() -> Engine:
    settings = Settings.from_env()
    # Workers do not issue HTTP cursors; avoid a Secrets Manager permission here.
    return Engine(Domain(DynamoStore(settings), settings, Cursors(b"unused-worker-cursor-key" * 2)))
