"""Canonical sourced memory; derived search results are always reauthorized and rehydrated."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from koyori.domain import hkey, projection, row, uid
from koyori.errors import Problem, missing
from koyori.stage2 import Service
from koyori.store import guard, put, revised


class Memory(Service):
    def get(self, ctx, mid, *, owner=False, tombstone=False):
        item = self.store.get("Domain", (hkey(ctx.h), f"MEMORY#{mid}"))
        if not item or (item.get("deleted") and not tombstone):
            raise missing()
        own = item["owner"] == ctx.actor and ctx.profile["kind"] == "personal"
        if not own and (owner or item["visibility"] != "household"):
            raise missing()
        if not tombstone and item.get("validUntil") and item["validUntil"] <= self.domain.now():
            raise missing()
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
        return item, [guard("Domain", item)] if item else []

    def create(self, ctx, body):
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
        if item["key"] and item["kind"] != "exchange":
            slot_key = (hkey(ctx.h), f"MEMKEY#{ctx.actor}#{item['kind']}#{item['key']}")
            slot = self.store.get("Domain", slot_key)
            if slot and not slot.get("deleted"):
                raise Problem(409, "MEMORY_KEY_EXISTS", "Correct the existing keyed memory.")
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
        if delete and old["key"] and old["kind"] != "exchange":
            slot = self.store.get(
                "Domain", (hkey(ctx.h), f"MEMKEY#{ctx.actor}#{old['kind']}#{old['key']}")
            )
            if slot:
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
        items = []
        for item in rows:
            try:
                items.append(projection(self.get(ctx, item["id"])))
            except Problem as exc:
                if exc.status != 404:
                    raise
        return {
            "items": items,
            "nextCursor": self.domain.cursors.encode(ctx.actor, ctx.h, "memory", last)
            if last
            else None,
        }

    def context(self, ctx, body, semantic=None):
        """Return a bounded source-backed context. Day boundaries follow local civil time."""
        zone = ZoneInfo(ctx.profile.get("timeZone", ctx.household["timeZone"]))
        start = end = None
        if body.get("day"):
            day = (
                datetime.fromtimestamp(self.domain.now(), zone).date() - timedelta(days=1)
                if body["day"] == "yesterday"
                else date.fromisoformat(body["day"])
            )
            start = int(datetime.combine(day, time(), zone).timestamp())
            end = int(datetime.combine(day + timedelta(days=1), time(), zone).timestamp())
        rows, after, scanned = [], None, 0
        partitions = [(hkey(ctx.h), "MEMTIME#")]
        if start is not None:
            first = datetime.fromtimestamp(start, UTC).date()
            last = datetime.fromtimestamp(end - 1, UTC).date()
            partitions = [
                (f"MEMDAY#{ctx.h}#{(first + timedelta(days=i)).isoformat()}", "")
                for i in range((last - first).days + 1)
            ]
        archive_truncated = False
        for pk, prefix in partitions:
            after = None
            while scanned < 500:
                page, after = self.store.query(
                    "Domain", pk, prefix=prefix, after=after, limit=50, descending=True
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
        semantic_status = "not-requested"
        if body.get("query") and semantic and len(candidates) < body["limit"]:
            try:
                recalled = semantic.search(ctx, body["query"])
                semantic_status = "available"
            except Problem as exc:
                if exc.status not in {429, 503}:
                    raise
                recalled = []
                semantic_status = exc.code
            for candidate in recalled:
                if (start is None or start <= candidate["occurredAt"] < end) and (
                    not body.get("key") or candidate.get("key") == body["key"]
                ):
                    candidates.append(candidate)
        unique = {item["id"]: item for item in candidates}
        selected, missing_sources, used = [], [], 0
        for item in sorted(unique.values(), key=lambda x: (x["occurredAt"], x["id"]), reverse=True):
            linked = None
            try:
                linked = self.source(ctx, item["source"])
            except Problem as exc:
                if exc.status not in {403, 404}:
                    raise
                missing_sources.append(item["id"])
            value = projection(item)
            value["sourceStatus"] = (
                "available" if linked or item["source"]["kind"] == "declaration" else "absent"
            )
            if linked:
                value["linkedState"] = {
                    k: linked[k] for k in ("id", "rev", "status", "receipt") if k in linked
                }
            import json

            size = len(json.dumps(value, ensure_ascii=False))
            if used + size > body["maxCharacters"]:
                continue
            selected.append(value)
            used += size
            if len(selected) >= body["limit"]:
                break
        return {
            "items": selected,
            "missingSources": missing_sources[:8],
            "truncated": archive_truncated or len(unique) > len(selected),
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
