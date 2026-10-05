"""Local service readiness retries, then deliberate idempotent initialization."""

import json
import time

from koyori.config import Settings
from koyori.demo import seed


def main():
    settings = Settings.from_env()
    if settings.env != "local":
        raise ValueError("Bootstrap is local only")
    for attempt in range(30):
        try:
            settings.client("dynamodb").list_tables(Limit=1)
            settings.client("sqs").list_queues(MaxResults=1)
            break
        except Exception:
            if attempt == 29:
                raise RuntimeError("Local services did not become ready") from None
            time.sleep(2)
    print(json.dumps(seed(settings), ensure_ascii=False))


if __name__ == "__main__":
    main()
