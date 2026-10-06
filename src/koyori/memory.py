"""Canonical sourced memory; derived search results are always reauthorized and rehydrated."""

import json
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from koyori.domain import hkey, projection, row, uid
from koyori.errors import Problem, missing
from koyori.stage2 import Service
from koyori.stage2_contracts import MemoryPatch
from koyori.store import Change, guard, put, revised


class Memory(Service):
    def get(self, ctx, mid, *, owner=False, tombstone=False):
        item = self.store.get("Domain", (hkey(ctx.h), f"MEMORY#{mid}"))
        if not item or (item.get("deleted") and not tombstone):
            raise missing()
        fence = self.store.get("Domain", (hkey(ctx.h), f"PRIVACY#{item['owner']}"))
        if not tombstone and fence and fence["status"] == "ERASING":
            raise missing()
        own = item["owner"] == ctx.actor and ctx.profile["kind"] == "personal"
        if not own and (owner or item["visibility"] != "household"):
            raise missing()
        if not tombstone and item.get("validUntil") and item["validUntil"] <= self.domain.now():
            raise missing()
        return item

    def read_checks(self, ctx, item):
        """A disclosure must lose to erasure accepted after its content was read."""
        key = (hkey(ctx.h), f"PRIVACY#{item['owner']}")
        fence = self.store.get("Domain", key)
        if fence and fence["status"] == "ERASING":
            raise missing()
        return [
            guard("Domain", item),
            guard("Domain", fence) if fence else Change("Domain", key, None),
        ]

    def disclosure_fence(self):
        key = ("RESTORE_FENCE", "META")
        fence = self.store.get("Sessions", key)
        if fence and fence.get("blocked"):
            raise Problem(503, "RESTORE_OFFLINE", "Restored namespace is offline.")
        return [guard("Sessions", fence) if fence else Change("Sessions", key, None)]

    def day_range(self, ctx, value=None):
        zone = ZoneInfo(ctx.profile.get("timeZone", ctx.household["timeZone"]))
        if not value:
            return None, None, zone
        day = (
            datetime.fromtimestamp(self.domain.now(), zone).date() - timedelta(days=1)
            if value == "yesterday"
            else date.fromisoformat(value)
        )
        return (
            int(datetime.combine(day, time(), zone).timestamp()),
            int(datetime.combine(day + timedelta(days=1), time(), zone).timestamp()),
            zone,
        )

    def context_value(self, ctx, item):
        value = projection(item)
        checks = self.read_checks(ctx, item)
        try:
            linked, authority = self.source_authority(ctx, item["source"])
        except Problem as exc:
            if exc.status not in {403, 404}:
                raise
            linked, authority = None, []
        value["sourceStatus"] = (
            "available" if linked or item["source"]["kind"] == "declaration" else "absent"
        )
        if linked:
            value["linkedState"] = {
                k: linked[k] for k in ("id", "rev", "status", "receipt") if k in linked
            }
        return value, checks + authority

    def core(self, ctx, body, keys=()):
        """Read stable slots rather than the recent exchange archive; never persist a prompt copy."""
        from koyori.lexical import words

        entries, scanned, truncated = {}, 0, False
        requested = set(keys) | ({body["key"]} if body.get("key") else set())
        # Direct lookups ensure explicit keys survive a bounded slot discovery.
        slots = []
        for actor in ctx.household["memberIds"]:
            for kind in ("preference", "procedure"):
                for key in requested:
                    slot = self.store.get("Domain", (hkey(ctx.h), f"MEMKEY#{actor}#{kind}#{key}"))
                    if slot:
                        slots.append(slot)
        for actor in ctx.household["memberIds"]:
            after = None
            while scanned < 500:
                page, after = self.store.query(
                    "Domain",
                    hkey(ctx.h),
                    prefix=f"MEMKEY#{actor}#",
                    after=after,
                    limit=min(50, 500 - scanned),
                )
                slots.extend(page)
                scanned += len(page)
                if not after:
                    break
            truncated |= bool(after) or scanned >= 500
        for slot in slots:
            if slot.get("deleted"):
                continue
            try:
                item = self.get(ctx, slot["memoryId"])
            except Problem as exc:
                if exc.status != 404:
                    raise
                continue
            if body.get("key") and item["key"] != body["key"]:
                continue
            entries[item["id"]] = item
        terms = words(body.get("query") or "")
        ranked = sorted(
            entries.values(),
            key=lambda x: (
                x["key"] in requested,
                len(terms & words(x["text"])),
                ctx.profile["kind"] == "personal" and x["owner"] == ctx.actor,
                x["kind"] == "preference",
                x["updatedAt"],
                x["id"],
            ),
            reverse=True,
        )
        selected, checks, used = [], [], 0
        budget = min(8000, body["maxCharacters"])
        for item in ranked:
            value, authority = self.context_value(ctx, item)
            size = len(json.dumps(value, ensure_ascii=False))
            if value["sourceStatus"] != "available" or used + size > budget:
                truncated = True
                continue
            selected.append(value)
            checks.extend(authority)
            used += size
            if len(selected) == 8:
                break
        return selected, checks, used, truncated or len(entries) > len(selected)

    def read(self, ctx, mid):
        item = self.get(ctx, mid)
        self.store.transact(ctx.guards() + self.read_checks(ctx, item))
        return item

    def index_intent(self, item, old=None):
        return row(
            f"MEMINDEX#{item['id']}",
            rev=old["rev"] + 1 if old else 1,
            h=item["PK"][2:],
            memoryId=item["id"],
            memoryRev=item["rev"],
            status="PENDING",
            GSI1PK=f"{'MEMERASE' if item['deleted'] else 'MEMINDEX'}#{int(item['id'][:8], 16) % self.domain.settings.shards}",
            GSI1SK=f"{self.domain.now():020d}#{item['id']}",
        )

    def source(self, ctx, source):
        if source["kind"] == "declaration":
            return None
        if source["kind"] == "memory":
            return self.get(ctx, source["id"])
        if source["kind"] == "task":
            return self.domain.task_access(ctx, source["id"])[0]
        from koyori.actions import Actions

        return Actions(self.domain).get(ctx, "ACTION", source["id"])

    def source_authority(self, ctx, source):
        if source["kind"] == "task":
            return self.domain.task_access(ctx, source["id"])
        item = self.source(ctx, source)
        if source["kind"] == "memory":
            return item, self.read_checks(ctx, item)
        return item, [guard("Domain", item)] if item else []

    def create(self, ctx, body):
        from koyori.privacy import memory_fence

        fence = memory_fence(self, ctx)
        now = self.domain.now()
        if body.get("occurredAt") and body["occurredAt"] > now:
            raise Problem(422, "INVALID_TIME", "An exchange cannot be in the future.")
        if body.get("validUntil") and body["validUntil"] <= now:
            raise Problem(422, "INVALID_TIME", "Memory validity must be in the future.")
        source, source_checks = self.source_authority(ctx, body["source"])
        if body["visibility"] == "household" and source and source.get("visibility") != "household":
            raise Problem(403, "PRIVATE_SOURCE", "A private source cannot become shared memory.")
        mid = uid()
        item = row(
            hkey(ctx.h),
            f"MEMORY#{mid}",
            id=mid,
            owner=ctx.actor,
            kind=body["kind"],
            text=body["text"],
            key=body.get("key"),
            steps=body.get("steps", []),
            source=body["source"],
            sourceRevision=source["rev"] if source else None,
            visibility=body["visibility"],
            occurredAt=body.get("occurredAt") or now,
            createdAt=now,
            updatedAt=now,
            validUntil=body.get("validUntil"),
            author=ctx.actor,
            channel=ctx.profile["kind"],
            privacyEpoch=1,
            deleted=False,
        )
        writes = [
            fence,
            put("Domain", item),
            put("Domain", row(hkey(ctx.h), f"MEMTIME#{item['occurredAt']:020d}#{mid}", id=mid)),
            put(
                "Domain",
                row(
                    f"MEMDAY#{ctx.h}#{datetime.fromtimestamp(item['occurredAt'], UTC).date().isoformat()}",
                    f"{item['occurredAt']:020d}#{mid}",
                    id=mid,
                ),
            ),
            put("Delivery", self.index_intent(item)),
            self.domain.event(ctx, mid, 1, kind="memory"),
        ]
        writes.extend(source_checks)
        from koyori.auto_learning import AutoLearning
        from koyori.lexical import Lexical

        writes.extend(Lexical(self.domain).enqueue(item))
        writes.extend(AutoLearning(self.domain).enqueue(ctx, item, "memory"))
        if item["key"] and item["kind"] != "exchange":
            slot_key = (hkey(ctx.h), f"MEMKEY#{ctx.actor}#{item['kind']}#{item['key']}")
            slot = self.store.get("Domain", slot_key)
            if slot and not slot.get("deleted"):
                prior = self.store.get("Domain", (hkey(ctx.h), f"MEMORY#{slot['memoryId']}"))
                if not prior or not (
                    prior["deleted"] or prior.get("validUntil") and prior["validUntil"] <= now
                ):
                    raise Problem(409, "MEMORY_KEY_EXISTS", "Correct the existing keyed memory.")
                # Reusing the slot must lose to a concurrent renewal of its memory.
                writes.append(guard("Domain", prior))
            writes.append(
                put(
                    "Domain",
                    row(*slot_key, rev=slot["rev"] + 1 if slot else 1, memoryId=mid, deleted=False),
                    slot,
                )
            )
        return {"id": mid, "rev": 1}, writes, item["visibility"] == "household"

    def change(self, ctx, mid, body, version, *, delete=False):
        old = self.get(ctx, mid, owner=True, tombstone=True)
        self.domain.require_version(old, version)
        if old["deleted"]:
            raise Problem(409, "MEMORY_DELETED", "The memory has already been erased.")
        if not delete:
            from koyori.privacy import memory_fence

            fence = memory_fence(self, ctx)
            try:
                body = MemoryPatch.model_validate(
                    {k: body.get(k, old[k]) for k in ("text", "steps", "visibility", "validUntil")}
                ).model_dump()
            except ValidationError:
                raise Problem(
                    422, "INVALID_MEMORY", "Merged memory exceeds the content bounds."
                ) from None
            if body.get("validUntil") and body["validUntil"] <= self.domain.now():
                raise Problem(422, "INVALID_TIME", "Memory validity must be in the future.")
            if (old["kind"] == "procedure") != bool(body["steps"]):
                raise Problem(422, "INVALID_PROCEDURE", "Only procedures have steps.")
            source, source_checks = self.source_authority(ctx, old["source"])
            if (
                body["visibility"] == "household"
                and source
                and source.get("visibility") != "household"
            ):
                raise Problem(403, "PRIVATE_SOURCE", "The source is private.")
            if old["key"] and old["kind"] != "exchange":
                slot = self.store.get(
                    "Domain", (hkey(ctx.h), f"MEMKEY#{ctx.actor}#{old['kind']}#{old['key']}")
                )
                if not slot or slot.get("deleted") or slot["memoryId"] != mid:
                    raise Problem(409, "MEMORY_KEY_REPLACED", "This keyed memory was replaced.")
                # A prepared renewal cannot revive an expired record after replacement.
                source_checks.append(guard("Domain", slot))
        else:
            source = None
            source_checks = []
        new = revised(
            old,
            updatedAt=self.domain.now(),
            privacyEpoch=old["privacyEpoch"] + 1,
            **(
                {"deleted": True, "text": "", "steps": [], "source": {"kind": "erased"}}
                if delete
                else {k: body[k] for k in ("text", "steps", "visibility", "validUntil")}
            ),
        )
        intent = self.store.get("Delivery", (f"MEMINDEX#{mid}", "META"))
        writes = [
            put("Domain", new, old),
            put("Delivery", self.index_intent(new, intent), intent),
            self.domain.event(ctx, mid, new["rev"], kind="memory"),
        ]
        writes.extend(source_checks)
        from koyori.auto_learning import AutoLearning
        from koyori.lexical import Lexical

        writes.extend(Lexical(self.domain).enqueue(new))
        if not delete:
            writes.extend(AutoLearning(self.domain).enqueue(ctx, new, "memory"))
        if not delete:
            writes.append(fence)
        if delete and old["key"] and old["kind"] != "exchange":
            slot = self.store.get(
                "Domain", (hkey(ctx.h), f"MEMKEY#{ctx.actor}#{old['kind']}#{old['key']}")
            )
            if slot and slot["memoryId"] == mid:
                writes.append(put("Domain", revised(slot, deleted=True), slot))
        return (
            {"id": mid, "rev": new["rev"], "deleted": delete},
            writes,
            (not delete and old["visibility"] != "household" and new["visibility"] == "household"),
        )

    def list(self, ctx, cursor=None):
        after = self.domain.cursors.decode(cursor, ctx.actor, ctx.h, "memory")
        rows, last = self.store.query(
            "Domain", hkey(ctx.h), prefix="MEMTIME#", after=after, limit=50
        )
        items, checks = [], []
        for item in rows:
            try:
                current = self.get(ctx, item["id"])
                checks.extend(self.read_checks(ctx, current))
                items.append(projection(current))
            except Problem as exc:
                if exc.status != 404:
                    raise
        self.store.transact(ctx.guards() + checks)
        return {
            "items": items,
            "nextCursor": self.domain.cursors.encode(ctx.actor, ctx.h, "memory", last)
            if last
            else None,
        }

    def context(self, ctx, body, semantic=None):
        """Return a bounded source-backed context. Day boundaries follow local civil time."""
        start, end, zone = self.day_range(ctx, body.get("day"))
        core, core_checks, core_used, core_truncated = (
            self.core(ctx, body) if body.get("includeCore") else ([], [], 0, False)
        )
        rows, after, scanned = [], None, 0
        partitions = [(hkey(ctx.h), "MEMTIME#")]
        if start is not None:
            epoch = datetime(1970, 1, 1, tzinfo=UTC)
            # Arithmetic avoids the narrower platform C timestamp range on Windows.
            first = (epoch + timedelta(seconds=start)).date()
            last = (epoch + timedelta(seconds=end - 1)).date()
            partitions = [
                (f"MEMDAY#{ctx.h}#{(first + timedelta(days=i)).isoformat()}", "")
                for i in reversed(range((last - first).days + 1))
            ]
        archive_truncated = False
        for pk, prefix in partitions:
            after = None
            while scanned < 500:
                page, after = self.store.query(
                    "Domain",
                    pk,
                    prefix=prefix,
                    after=after,
                    limit=min(50, 500 - scanned),
                    descending=True,
                )
                scanned += len(page)
                rows.extend(page)
                if not after:
                    break
            archive_truncated |= bool(after) or scanned >= 500
        candidates = []
        if body.get("key"):
            for actor in ctx.household["memberIds"]:
                for kind in ("preference", "procedure"):
                    slot = self.store.get(
                        "Domain", (hkey(ctx.h), f"MEMKEY#{actor}#{kind}#{body['key']}")
                    )
                    if slot and not slot.get("deleted"):
                        rows.append({"id": slot["memoryId"]})
        for item in rows:
            try:
                current = self.get(ctx, item["id"])
            except Problem as exc:
                if exc.status == 404:
                    continue
                raise
            if start is not None and not start <= current["occurredAt"] < end:
                continue
            if body.get("key") and current.get("key") != body["key"]:
                continue
            if body.get("query") and body["query"].casefold() not in current["text"].casefold():
                continue
            candidates.append(current)
        lexical_incomplete = False
        if body.get("query"):
            from koyori.lexical import Lexical, words

            terms = sorted(words(body["query"]), key=lambda t: (-len(t), t))
            if terms:
                lexical = Lexical(self.domain).search(
                    ctx, {**body, "query": " ".join(terms[:8]), "cursor": None, "kinds": []}
                )
                lexical_incomplete = lexical["truncated"] or len(terms) > 8
                for found in lexical["items"]:
                    try:
                        candidates.append(self.get(ctx, found["id"]))
                    except Problem as exc:
                        if exc.status != 404:
                            raise
        semantic_status = "not-requested"
        semantic_rank = {}
        if body.get("query") and semantic:
            try:
                recalled = semantic.search(ctx, body["query"])
                semantic_status = "available"
            except Problem as exc:
                if exc.status not in {429, 503}:
                    raise
                recalled = []
                semantic_status = exc.code
            for rank, candidate in enumerate(recalled):
                if (start is None or start <= candidate["occurredAt"] < end) and (
                    not body.get("key") or candidate.get("key") == body["key"]
                ):
                    candidates.append(candidate)
                    semantic_rank[candidate["id"]] = len(recalled) - rank
        unique = {item["id"]: item for item in candidates}
        selected, missing_sources, used, checks = [], [], core_used, list(core_checks)
        from koyori.lexical import words

        terms = words(body.get("query") or "")
        for item in sorted(
            unique.values(),
            key=lambda x: (
                len(terms & words(x["text"])),
                semantic_rank.get(x["id"], 0),
                x["occurredAt"],
                x["id"],
            ),
            reverse=True,
        ):
            if item["id"] in {c["id"] for c in core}:
                continue
            value, authority = self.context_value(ctx, item)
            if value["sourceStatus"] == "absent":
                missing_sources.append(item["id"])
            size = len(json.dumps(value, ensure_ascii=False))
            if used + size > body["maxCharacters"]:
                continue
            selected.append(value)
            checks.extend(authority)
            used += size
            if len(selected) >= min(body["limit"], 14 - len(core)):
                break
        self.store.transact(ctx.guards() + self.disclosure_fence() + checks)
        return {
            "items": selected,
            "coreItems": core,
            "coreTruncated": core_truncated,
            "missingSources": missing_sources[:8],
            "truncated": archive_truncated
            or lexical_incomplete
            or core_truncated
            or bool(set(unique) - {i["id"] for i in selected + core}),
            "timeZone": str(zone),
            "range": {"start": start, "end": end},
            "characters": used,
            "generatedAt": datetime.fromtimestamp(self.domain.now(), UTC).isoformat(),
            "semanticStatus": semantic_status,
        }

    def commitments(self, ctx, cursor=None):
        """Engagements use canonical task/action state; they cannot be declared successful."""
        from koyori.actions import Actions

        after = self.domain.cursors.decode(cursor, ctx.actor, ctx.h, "commitments")
        rows, last = self.store.query("Domain", hkey(ctx.h), after=after, limit=50)
        values = []
        for item in rows:
            try:
                if item["SK"].startswith("TASK#"):
                    current = self.domain.task_access(ctx, item["id"])[0]
                elif item["SK"].startswith("ACTION#"):
                    current = Actions(self.domain).get(ctx, "ACTION", item["id"])
                else:
                    continue
                values.append(
                    {
                        "kind": "commitment",
                        "source": item["SK"].split("#")[0].lower(),
                        **{
                            k: current[k]
                            for k in ("id", "rev", "status", "receipt", "dueAt")
                            if k in current
                        },
                    }
                )
            except Problem as exc:
                if exc.status not in {403, 404}:
                    raise
        return {
            "items": values,
            "nextCursor": self.domain.cursors.encode(ctx.actor, ctx.h, "commitments", last)
            if last
            else None,
        }
