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


def erasure_ledger(store):
    """Capture suppression keys from the current offline source, including post-backup deletions."""
    records, after = [], None
    while True:
        args = dict(TableName=store.name("Domain"), ConsistentRead=True, Limit=100)
        if after:
            args["ExclusiveStartKey"] = after
        response = store.client.scan(**args)
        for raw in response["Items"]:
            item = store.decode(raw)
            if item["SK"].startswith("PRIVACY#") and item.get("status") == "ERASING":
                raise ValueError("Complete pending memory erasures before capturing a ledger")
            if item["SK"].startswith("MEMORY#") and item.get("deleted"):
                records.append({"PK": item["PK"], "SK": item["SK"], "revision": item["rev"]})
        after = response.get("LastEvaluatedKey")
        if not after:
            break
    entries = sorted(records, key=lambda item: (item["PK"], item["SK"]))
    return {
        "schemaVersion": "1.0",
        "sourcePrefix": store.prefix,
        "entries": entries,
        "sha256": hashlib.sha256(
            json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def apply_suppressions(tables, ledger, *, shards=4):
    """Restore never revives sessions, approvals or erased memory; external effects stay fenced."""
    entries = ledger["entries"]
    if (
        ledger.get("schemaVersion") != "1.0"
        or hashlib.sha256(
            json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        != ledger["sha256"]
    ):
        raise ValueError("Erasure ledger integrity failure")
    suppressed = {(entry["PK"], entry["SK"]): entry["revision"] for entry in entries}
    memories = set()
    for item in tables["Domain"]:
        if (item["PK"], item["SK"]) in suppressed:
            item.update(
                deleted=True,
                text="",
                steps=[],
                source={"kind": "erased"},
                rev=max(item["rev"], suppressed[(item["PK"], item["SK"])]),
                privacyEpoch=item.get("privacyEpoch", 1) + 1,
            )
            memories.add(item.get("id"))
        if item["SK"].startswith("CONNECTION#"):
            item.update(active=False, revoked=True)
    tables["Sessions"] = [
        item
        for item in tables["Sessions"]
        if item["PK"].startswith(("IDEMP", "CONVERSATION#", "VOICETURN#", "VOICEUSAGE#"))
    ]
    # Backed-up provider credentials must be re-linked, never silently reactivated.
    tables["Connections"] = []
    for item in tables["Delivery"]:
        if item["PK"].startswith("MEMINDEX#") and item.get("memoryId") in memories:
            item.update(
                status="PENDING",
                memoryRev=suppressed[(f"H#{item['h']}", f"MEMORY#{item['memoryId']}")],
                GSI1PK=f"MEMERASE#{int(item['memoryId'][:8], 16) % shards}",
                GSI1SK=f"{0:020d}#{item['memoryId']}",
            )
    indexed = {
        item["memoryId"] for item in tables["Delivery"] if item["PK"].startswith("MEMINDEX#")
    }
    for item in tables["Domain"]:
        if item.get("id") in memories and item["id"] not in indexed:
            mid = item["id"]
            tables["Delivery"].append(
                {
                    "PK": f"MEMINDEX#{mid}",
                    "SK": "META",
                    "rev": 1,
                    "h": item["PK"][2:],
                    "memoryId": mid,
                    "memoryRev": item["rev"],
                    "status": "PENDING",
                    "GSI1PK": f"MEMERASE#{int(mid[:8], 16) % shards}",
                    "GSI1SK": f"{0:020d}#{mid}",
                }
            )
    return tables


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
        "shards": store.shards,
        "sha256": hashlib.sha256(data).hexdigest(),
        "tables": tables,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exports contain domain data and grant responses; never write under tracked docs.
    with path.open("x", encoding="utf-8") as output:
        json.dump(snapshot, output, ensure_ascii=False)
    path.chmod(0o600)
    return {"sha256": snapshot["sha256"], "counts": {k: len(v) for k, v in tables.items()}}


def restore_local(store: DynamoStore, path: Path, *, erasure_overlay: dict | None = None) -> dict:
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
    if not erasure_overlay or erasure_overlay.get("sourcePrefix") != snapshot["sourcePrefix"]:
        raise ValueError("A current erasure ledger from the stopped source is required")
    if snapshot.get("shards", 4) != store.shards:
        raise ValueError("Restore must preserve the source shard configuration")
    tables = apply_suppressions(tables, erasure_overlay, shards=store.shards)
    # Refuse existing target tables before any write; a partial restore stays offline.
    for table in tables:
        try:
            store.client.describe_table(TableName=store.name(table))
        except store.client.exceptions.ResourceNotFoundException:
            continue
        raise ValueError("Target namespace already exists")
    store.create_tables()
    # Keep this namespace offline until canonical provider reconciliation is reviewed.
    store.transact(
        [
            put(
                "Sessions",
                {
                    "PK": "RESTORE_FENCE",
                    "SK": "META",
                    "rev": 1,
                    "sourceSha256": snapshot["sha256"],
                    "blocked": True,
                },
            )
        ]
    )
    for table, items in tables.items():
        for start in range(0, len(items), 50):
            store.transact([put(table, item) for item in items[start : start + 50]])
    return {"sha256": snapshot["sha256"], "counts": {k: len(v) for k, v in tables.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["export", "restore", "ledger"])
    parser.add_argument("path", type=Path)
    parser.add_argument("--writers-stopped", action="store_true", required=True)
    parser.add_argument("--target-prefix")
    parser.add_argument("--erasure-ledger", type=Path)
    args = parser.parse_args()
    settings = Settings.from_env()
    if settings.env != "local":
        parser.error("Local-only backup; use the AWS recovery runbook for deployed data")
    if args.command == "restore":
        if not args.target_prefix:
            parser.error("A new --target-prefix is required")
        settings = replace(settings, prefix=args.target_prefix)
    store = DynamoStore(settings)
    if args.command == "ledger":
        with args.path.open("x", encoding="utf-8") as output:
            json.dump(erasure_ledger(store), output)
        args.path.chmod(0o600)
        print("Current erasure ledger exported")
        return
    if args.command == "restore" and not args.erasure_ledger:
        parser.error("Restore requires --erasure-ledger from the current stopped source")
    print(
        json.dumps(
            export_local(store, args.path)
            if args.command == "export"
            else restore_local(
                store,
                args.path,
                erasure_overlay=json.loads(args.erasure_ledger.read_text(encoding="utf-8")),
            )
        )
    )


if __name__ == "__main__":
    main()
