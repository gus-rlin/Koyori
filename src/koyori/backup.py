"""Offline local export/restore into a new namespace, with a verified manifest.

Operators must stop all mutating processes first. This is not an online backup
protocol and cannot establish a consistent snapshot while writers are active.
"""

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path

from koyori.config import Settings
from koyori.store import DynamoStore, put


def export_local(store: DynamoStore, path: Path) -> dict:
    tables = {}
    for table in ("Domain", "Delivery", "Sessions", "Connections"):
        items, after = [], None
        while True:
            args = dict(TableName=store.name(table), ConsistentRead=True, Limit=100)
            if after:
                args["ExclusiveStartKey"] = after
            response = store.client.scan(**args)
            items.extend(store.decode(item) for item in response["Items"])
            after = response.get("LastEvaluatedKey")
            if not after:
                break
        tables[table] = sorted(items, key=lambda item: (item["PK"], item["SK"]))
    data = json.dumps(tables, sort_keys=True, separators=(",", ":")).encode()
    snapshot = {
        "schemaVersion": "1.0",
        "mode": "synthetic-local",
        "sourcePrefix": store.prefix,
        "sha256": hashlib.sha256(data).hexdigest(),
        "tables": tables,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exports contain domain data and grant responses; never write under tracked docs.
    with path.open("x", encoding="utf-8") as output:
        json.dump(snapshot, output, ensure_ascii=False)
    path.chmod(0o600)
    return {"sha256": snapshot["sha256"], "counts": {k: len(v) for k, v in tables.items()}}


def restore_local(store: DynamoStore, path: Path) -> dict:
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    if (
        snapshot.get("schemaVersion") != "1.0"
        or snapshot.get("mode") != "synthetic-local"
        or snapshot["sourcePrefix"] == store.prefix
    ):
        raise ValueError("Restore requires a new local table namespace")
    tables = snapshot["tables"]
    if set(tables) not in (
        {"Domain", "Delivery", "Sessions"},
        {"Domain", "Delivery", "Sessions", "Connections"},
    ):
        raise ValueError("Incomplete snapshot")
    data = json.dumps(tables, sort_keys=True, separators=(",", ":")).encode()
    if hashlib.sha256(data).hexdigest() != snapshot["sha256"]:
        raise ValueError("Snapshot integrity failure")
    # Refuse existing target tables before any write; a partial restore stays offline.
    for table in tables:
        try:
            store.client.describe_table(TableName=store.name(table))
        except store.client.exceptions.ResourceNotFoundException:
            continue
        raise ValueError("Target namespace already exists")
    store.create_tables()
    for table, items in tables.items():
        for start in range(0, len(items), 50):
            store.transact([put(table, item) for item in items[start : start + 50]])
    return {"sha256": snapshot["sha256"], "counts": {k: len(v) for k, v in tables.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["export", "restore"])
    parser.add_argument("path", type=Path)
    parser.add_argument("--writers-stopped", action="store_true", required=True)
    parser.add_argument("--target-prefix")
    args = parser.parse_args()
    settings = Settings.from_env()
    if settings.env != "local":
        parser.error("Local-only backup; use the AWS recovery runbook for deployed data")
    if args.command == "restore":
        if not args.target_prefix:
            parser.error("A new --target-prefix is required")
        settings = replace(settings, prefix=args.target_prefix)
    store = DynamoStore(settings)
    print(
        json.dumps(
            export_local(store, args.path)
            if args.command == "export"
            else restore_local(store, args.path)
        )
    )


if __name__ == "__main__":
    main()
