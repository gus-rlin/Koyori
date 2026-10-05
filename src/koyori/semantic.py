"""Bounded derived index. Local hashing is a fixture, not qualified semantic retrieval."""

import hashlib
import json
import logging
import math
import re
from datetime import UTC, datetime

from koyori.domain import hkey, row, uid
from koyori.errors import Conflict, Problem
from koyori.memory import Memory
from koyori.stage2 import Service
from koyori.store import guard, put, revised


def scope(h, owner, visibility):
    return f"H#{h}#SHARED" if visibility == "household" else f"H#{h}#P#{owner}"


class Semantic(Service):
    def __init__(self, domain, *, bedrock=None, vectors=None):
        super().__init__(domain)
        self.settings = domain.settings
        self.mode = self.settings.semantic_mode
        self.bedrock, self.vectors = bedrock, vectors

    def charge(self, h):
        if self.mode != "aws":
            return
        day = datetime.fromtimestamp(self.domain.now(), UTC).date().isoformat()
        key = (f"EMBEDUSE#{h}#{day}", "META")
        for _ in range(6):
            old = self.store.get("Domain", key)
            calls = old["calls"] if old else 0
            if calls >= self.settings.embedding_daily_limit:
                raise Problem(
                    429, "EMBEDDING_BUDGET_EXHAUSTED", "Daily embedding call ceiling reached."
                )
            new = row(*key, rev=old["rev"] + 1 if old else 1, calls=calls + 1, day=day)
            try:
                self.store.transact([put("Domain", new, old)])
                return
            except Conflict:
                continue
        raise Problem(503, "CONTENTION", "Embedding reservation contention.", True)

    def embed(self, text):
        if self.mode == "disabled":
            raise Problem(503, "SEMANTIC_UNAVAILABLE", "Semantic search is not configured.")
        if self.mode == "simulated":
            result = [0] * 512
            for word in re.findall(r"\w+", text.casefold()):
                hashed = hashlib.sha256(word.encode()).digest()
                result[int.from_bytes(hashed[:2]) % 512] += 1 if hashed[2] % 2 else -1
            return result
        self.bedrock = self.bedrock or self.settings.client("bedrock-runtime")
        response = self.bedrock.invoke_model(
            modelId="amazon.titan-embed-text-v2:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps({"inputText": text, "dimensions": 512, "normalize": True}),
        )
        result = json.loads(response["body"].read())["embedding"]
        if len(result) != 512 or not all(
            isinstance(x, (float, int)) and math.isfinite(x) for x in result
        ):
            raise ValueError("Invalid embedding profile")
        return result

    def _client(self):
        self.vectors = self.vectors or self.settings.client("s3vectors")
        return self.vectors

    def completed_intent(self, memory, latest, *, removed):
        expires = memory.get("validUntil")
        if not removed and expires:
            # Expiration is a durable purge, including when it crossed during the put.
            due = max(self.domain.now(), expires)
            return revised(
                latest,
                status="PENDING",
                retries=0,
                dueAt=due,
                GSI1PK=f"MEMERASE#{int(memory['id'][:8], 16) % self.settings.shards}",
                GSI1SK=f"{due:020d}#{memory['id']}",
            )
        return self.domain.done_intent(latest)

    def repair_expired_candidate(self, ctx, mid):
        """Older DONE projections had no expiration schedule; repair only recalled IDs."""
        current = self.store.get("Domain", (hkey(ctx.h), f"MEMORY#{mid}"))
        if not current or current["deleted"] or not current.get("validUntil"):
            return
        if current["validUntil"] > self.domain.now():
            return
        latest = self.store.get("Delivery", (f"MEMINDEX#{mid}", "META"))
        if not latest or latest["status"] != "DONE":
            return
        try:
            self.store.transact(
                ctx.guards()
                + [
                    guard("Domain", current),
                    put("Delivery", self.completed_intent(current, latest, removed=False), latest),
                ]
            )
        except Conflict:
            return  # A renewal or another worker wins; its intent must be preserved.

    def finish_external(self, work, *, completed=False, recovery=False):
        """An independent durable record survives replacement of the main intent.

        An old external put/delete may finish after the newer revision was indexed.
        Rearm that revision even when its intent is DONE. A killed worker leaves
        this repair record pending, so the next worker also repairs after 120s.
        """
        for _ in range(6):
            current = self.store.get("Domain", (hkey(work["h"]), f"MEMORY#{work['memoryId']}"))
            latest = self.store.get("Delivery", (f"MEMINDEX#{work['memoryId']}", "META"))
            attempt = self.store.get("Delivery", (work["PK"], work["SK"]))
            if attempt["status"] == "DONE" and recovery:
                return
            if completed and current["rev"] == work["memoryRev"]:
                updated = self.completed_intent(
                    current, latest, removed=work.get("removed", current["deleted"])
                )
            else:
                updated = Memory(self.domain).index_intent(current, latest)
                if current["rev"] == latest["memoryRev"]:
                    updated["retries"] = latest.get("retries", 0)
            try:
                self.store.transact(
                    [
                        guard("Domain", current),
                        put("Delivery", updated, latest),
                        put("Delivery", self.domain.done_intent(attempt), attempt),
                    ]
                )
                return
            except Conflict:
                continue
        raise Problem(503, "CONTENTION", "Projection repair contention.", True)

    def project(self, intent):
        memory = self.store.get("Domain", (hkey(intent["h"]), f"MEMORY#{intent['memoryId']}"))
        if not memory:
            return
        if self.mode == "disabled":
            return
        removed = (
            memory["deleted"]
            or memory.get("validUntil")
            and memory["validUntil"] <= self.domain.now()
        )
        if not removed:
            self.charge(intent["h"])
        data = None if removed else self.embed(memory["text"])
        metadata = {
            "scopeKey": scope(intent["h"], memory["owner"], memory["visibility"]),
            "memoryId": memory["id"],
            "revision": memory["rev"],
            "privacyEpoch": memory["privacyEpoch"],
            "kind": memory["kind"],
            "occurredAt": memory["occurredAt"],
        }
        # Recheck immediately before the external write; canonical rehydration also
        # protects readers if a correction races with that unavoidable boundary.
        current = self.store.get("Domain", (memory["PK"], memory["SK"]))
        if current["rev"] != memory["rev"]:
            return
        writes = []
        if self.mode == "aws":
            # Persist the effect boundary before touching S3. This record cannot be
            # overwritten by correction/deletion or another projection of the memory.
            wid, due = uid(), self.domain.now() + 120
            work = row(
                f"MEMWORK#{wid}",
                h=intent["h"],
                memoryId=memory["id"],
                memoryRev=memory["rev"],
                removed=bool(removed),
                status="PENDING",
                dueAt=due,
                GSI1PK=f"MEMREPAIR#{int(wid[:8], 16) % self.settings.shards}",
                GSI1SK=f"{due:020d}#{wid}",
            )
            leased = revised(intent, dueAt=due, GSI1SK=f"{due:020d}#{memory['id']}")
            try:
                self.store.transact(
                    [
                        guard("Domain", memory),
                        put("Delivery", leased, intent),
                        put("Delivery", work),
                    ]
                )
            except Conflict:
                return
            args = {
                "vectorBucketName": self.settings.vector_bucket,
                "indexName": self.settings.vector_index,
            }
            try:
                if removed:
                    self._client().delete_vectors(**args, keys=[memory["id"]])
                else:
                    self._client().put_vectors(
                        **args,
                        vectors=[
                            {"key": memory["id"], "data": {"float32": data}, "metadata": metadata}
                        ],
                    )
            except Exception:
                self.finish_external(work)
                raise
            self.finish_external(work, completed=True)
            return
        else:
            key = (f"VECTOR#{intent['h']}", f"MEMORY#{memory['id']}")
            old = self.store.get("Domain", key)
            writes.append(
                put(
                    "Domain",
                    row(
                        *key,
                        rev=old["rev"] + 1 if old else 1,
                        metadata=metadata,
                        data=data or [],
                        deleted=bool(removed),
                    ),
                    old,
                )
            )
        latest = self.store.get("Delivery", (intent["PK"], intent["SK"]))
        if latest["rev"] != intent["rev"] or latest["memoryRev"] != memory["rev"]:
            return
        try:
            self.store.transact(
                writes
                + [
                    guard("Domain", memory),
                    put("Delivery", self.completed_intent(memory, latest, removed=removed), latest),
                ]
            )
        except Conflict:
            return  # The local vector and intent update share the canonical guard.

    def sweep(self):
        repairs = self.pending("MEMREPAIR")
        for work in repairs:
            try:
                self.finish_external(work, recovery=True)
            except Exception as exc:
                self.log_retry(exc)
        items = self.pending("MEMERASE") + self.pending("MEMINDEX")
        for item in items:
            try:
                self.project(item)
            except Exception as exc:
                self.log_retry(exc)
                latest = self.store.get("Delivery", (item["PK"], item["SK"]))
                if latest["status"] == "PENDING" and latest["memoryRev"] == item["memoryRev"]:
                    due = (
                        ((self.domain.now() // 86400) + 1) * 86400
                        if isinstance(exc, Problem) and exc.code == "EMBEDDING_BUDGET_EXHAUSTED"
                        else self.domain.now()
                        + min(3600, 30 * 2 ** min(latest.get("retries", 0), 7))
                    )
                    self.defer(latest, due)
        return len(items) + len(repairs)

    @staticmethod
    def log_retry(exc):
        logging.getLogger("koyori.projection").warning(
            json.dumps(
                {
                    "event": "projection_retry",
                    "errorClass": type(exc).__name__,
                    "code": exc.code if isinstance(exc, Problem) else "DEPENDENCY_UNAVAILABLE",
                }
            )
        )

    def search(self, ctx, text):
        self.charge(ctx.h)
        embedding = self.embed(text)
        scopes = [scope(ctx.h, ctx.actor, "private"), scope(ctx.h, ctx.actor, "household")]
        if ctx.profile["kind"] == "shared":
            scopes = scopes[1:]
        if self.mode == "aws":
            response = self._client().query_vectors(
                vectorBucketName=self.settings.vector_bucket,
                indexName=self.settings.vector_index,
                queryVector={"float32": embedding},
                topK=20,
                filter={"scopeKey": {"$in": scopes}},
                returnMetadata=True,
                returnDistance=True,
            )
            candidates = [x["metadata"] for x in response.get("vectors", [])]
        else:
            candidates, after, scanned = [], None, 0
            ranked = []
            while scanned < 500:
                page, after = self.store.query("Domain", f"VECTOR#{ctx.h}", after=after, limit=50)
                scanned += len(page)
                for vector in page:
                    if vector["deleted"] or vector["metadata"]["scopeKey"] not in scopes:
                        continue
                    norm = math.sqrt(
                        sum(x * x for x in embedding) * sum(x * x for x in vector["data"])
                    )
                    score = (
                        sum(a * b for a, b in zip(embedding, vector["data"], strict=True)) / norm
                        if norm
                        else 0
                    )
                    if score > 0:
                        ranked.append((score, vector["metadata"]))
                if not after:
                    break
            candidates = [x[1] for x in sorted(ranked, key=lambda x: x[0], reverse=True)[:20]]
        results = []
        for candidate in candidates[:20]:
            try:
                item = Memory(self.domain).get(ctx, candidate["memoryId"])
            except Problem as exc:
                if exc.status == 404:
                    self.repair_expired_candidate(ctx, candidate["memoryId"])
                    continue
                raise
            if (
                item["rev"] != candidate["revision"]
                or item["privacyEpoch"] != candidate["privacyEpoch"]
                or scope(ctx.h, item["owner"], item["visibility"]) != candidate["scopeKey"]
            ):
                continue
            if item["id"] not in {x["id"] for x in results}:
                results.append(item)
            if len(results) == 8:
                break
        return results
