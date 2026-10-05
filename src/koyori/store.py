"""DynamoDB transaction boundary and an equivalent deterministic test store.

Every row has a revision. A transaction checks the snapshots it used, including
authority rows; no caller writes through a cache or an index result.
"""

import copy
import json
import threading
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError

from koyori.config import Settings
from koyori.errors import Conflict

Key = tuple[str, str]


@dataclass
class Change:
    table: str
    key: Key
    expected: int | None
    item: dict | None = None  # None is a condition check, not a deletion.


def put(table: str, item: dict, previous: dict | None = None) -> Change:
    return Change(table, (item["PK"], item["SK"]), previous["rev"] if previous else None, item)


def guard(table: str, item: dict) -> Change:
    return Change(table, (item["PK"], item["SK"]), item["rev"])


def revised(item: dict, **values) -> dict:
    return {**item, **values, "rev": item["rev"] + 1}


class Store(Protocol):
    def get(self, table: str, key: Key) -> dict | None: ...
    def query(
        self,
        table: str,
        pk: str,
        *,
        prefix: str = "",
        after: dict | None = None,
        limit: int = 50,
        index: str | None = None,
    ) -> tuple[list[dict], dict | None]: ...
    def transact(self, changes: list[Change]) -> None: ...


def unique(changes: list[Change]) -> list[Change]:
    result = {}
    for change in changes:
        key = change.table, change.key
        old = result.get(key)
        if old and old.expected != change.expected:
            raise Conflict("Inconsistent transaction snapshots")
        if old and old.item and change.item and old.item != change.item:
            raise ValueError("Duplicate mutation")
        if not old or change.item:
            result[key] = change
    return list(result.values())


class DynamoStore:
    def __init__(self, settings: Settings):
        self.client = settings.client("dynamodb")
        self.prefix = settings.prefix
        self.serializer, self.deserializer = TypeSerializer(), TypeDeserializer()

    def name(self, table: str) -> str:
        return f"{self.prefix}{table}"

    def encode(self, item: dict) -> dict:
        return {key: self.serializer.serialize(value) for key, value in item.items()}

    def decode(self, item: dict) -> dict:
        def native(value):
            if isinstance(value, Decimal):
                return int(value)
            if isinstance(value, dict):
                return {k: native(v) for k, v in value.items()}
            if isinstance(value, list):
                return [native(v) for v in value]
            return value

        return native({k: self.deserializer.deserialize(v) for k, v in item.items()})

    def get(self, table: str, key: Key) -> dict | None:
        result = self.client.get_item(
            TableName=self.name(table),
            Key=self.encode(dict(zip(("PK", "SK"), key, strict=True))),
            ConsistentRead=True,
        )
        return self.decode(result["Item"]) if "Item" in result else None

    def query(
        self,
        table: str,
        pk: str,
        *,
        prefix: str = "",
        after: dict | None = None,
        limit: int = 50,
        index: str | None = None,
    ) -> tuple[list[dict], dict | None]:
        pk_name, sk_name = (f"{index}PK", f"{index}SK") if index else ("PK", "SK")
        args = dict(
            TableName=self.name(table),
            KeyConditionExpression="#pk = :pk",
            ExpressionAttributeNames={"#pk": pk_name},
            ExpressionAttributeValues=self.encode({":pk": pk}),
            Limit=limit,
            ConsistentRead=index is None,
        )
        if prefix:
            args["KeyConditionExpression"] += " AND begins_with(#sk, :prefix)"
            args["ExpressionAttributeNames"]["#sk"] = sk_name
            args["ExpressionAttributeValues"].update(self.encode({":prefix": prefix}))
        if index:
            args["IndexName"] = index
        if after:
            args["ExclusiveStartKey"] = self.encode(after)
        result = self.client.query(**args)
        return [self.decode(x) for x in result["Items"]], self.decode(
            result["LastEvaluatedKey"]
        ) if result.get("LastEvaluatedKey") else None

    def transact(self, changes: list[Change]) -> None:
        operations = []
        for change in unique(changes):
            args = dict(TableName=self.name(change.table))
            if change.expected is None:
                args["ConditionExpression"] = "attribute_not_exists(PK)"
            else:
                args.update(
                    ConditionExpression="#revision = :revision",
                    ExpressionAttributeNames={"#revision": "rev"},
                    ExpressionAttributeValues=self.encode({":revision": change.expected}),
                )
            if change.item is not None:
                if len(json.dumps(change.item).encode()) > 32768:
                    raise ValueError("Item exceeds application bound")
                args["Item"] = self.encode(change.item)
                operations.append({"Put": args})
            else:
                args["Key"] = self.encode({"PK": change.key[0], "SK": change.key[1]})
                operations.append({"ConditionCheck": args})
        try:
            self.client.transact_write_items(TransactItems=operations)
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            reasons = {r.get("Code") for r in exc.response.get("CancellationReasons", [])}
            if (
                code == "TransactionConflictException"
                or code == "TransactionCanceledException"
                and reasons <= {"None", "ConditionalCheckFailed", "TransactionConflict"}
            ):
                raise Conflict from None
            raise

    def create_tables(self) -> None:
        """Local bootstrap only; production tables are provisioned by IaC."""
        for table in ("Domain", "Delivery", "Sessions"):
            try:
                self.client.create_table(
                    TableName=self.name(table),
                    BillingMode="PAY_PER_REQUEST",
                    KeySchema=[
                        {"AttributeName": "PK", "KeyType": "HASH"},
                        {"AttributeName": "SK", "KeyType": "RANGE"},
                    ],
                    AttributeDefinitions=[
                        {"AttributeName": name, "AttributeType": "S"}
                        for name in ("PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK")
                    ],
                    GlobalSecondaryIndexes=[
                        {
                            "IndexName": index,
                            "KeySchema": [
                                {"AttributeName": f"{index}PK", "KeyType": "HASH"},
                                {"AttributeName": f"{index}SK", "KeyType": "RANGE"},
                            ],
                            "Projection": {"ProjectionType": "ALL"},
                        }
                        for index in ("GSI1", "GSI2")
                    ],
                )
            except self.client.exceptions.ResourceInUseException:
                pass
            self.client.get_waiter("table_exists").wait(TableName=self.name(table))


class MemoryStore:
    """Unit-test double, not a selectable runtime persistence mode."""

    def __init__(self):
        self.rows: dict[tuple[str, Key], dict] = {}
        self.lock = threading.RLock()

    def get(self, table: str, key: Key) -> dict | None:
        with self.lock:
            return copy.deepcopy(self.rows.get((table, key)))

    def query(
        self,
        table: str,
        pk: str,
        *,
        prefix: str = "",
        after: dict | None = None,
        limit: int = 50,
        index: str | None = None,
    ) -> tuple[list[dict], dict | None]:
        pk_name, sk_name = (f"{index}PK", f"{index}SK") if index else ("PK", "SK")
        with self.lock:
            rows = sorted(
                (
                    copy.deepcopy(v)
                    for (t, _), v in self.rows.items()
                    if t == table and v.get(pk_name) == pk and v.get(sk_name, "").startswith(prefix)
                ),
                key=lambda r: (r[sk_name], r["PK"], r["SK"]),
            )
            if after:
                rows = [
                    r
                    for r in rows
                    if (r[sk_name], r["PK"], r["SK"]) > (after[sk_name], after["PK"], after["SK"])
                ]
            page = rows[:limit]
            last = (
                {k: page[-1][k] for k in {"PK", "SK", pk_name, sk_name}}
                if len(rows) > limit
                else None
            )
            return page, last

    def transact(self, changes: list[Change]) -> None:
        with self.lock:
            changes = unique(changes)
            for change in changes:
                old = self.rows.get((change.table, change.key))
                if (old["rev"] if old else None) != change.expected:
                    raise Conflict
            for change in changes:
                if change.item is not None:
                    self.rows[(change.table, change.key)] = copy.deepcopy(change.item)
