"""Local fixture: stay live after a provider commit, before persisting its receipt."""

import sys
import time

from koyori.actions import Actions
from koyori.workers.runtime import engine


class Interrupted(Actions):
    def _finish(self, action, receipt):
        print("PROVIDER_COMMITTED", flush=True)
        time.sleep(600)


if __name__ == "__main__":
    Interrupted(engine().domain).run(sys.argv[1], sys.argv[2])
