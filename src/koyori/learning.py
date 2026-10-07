"""Sourced, reversible learning proposals. Acceptance changes memory, never permissions."""

from koyori.domain import hkey, projection, row, uid
from koyori.errors import Problem, missing
from koyori.memory import Memory
from koyori.notifications import Notifications
from koyori.stage2 import Service
from koyori.stage2_contracts import MemoryPatch, MemoryWrite
from koyori.store import Change, guard, put, revised


class Learning(Service):
    def get(self, ctx, identifier):
        self.domain.personal(ctx)
        item = self.store.get("Domain", (hkey(ctx.h), f"LEARNING#{identifier}"))
        if not item or item["owner"] != ctx.actor:
            raise missing()
        return item

    def propose(self, ctx, body, *, origin="manual", mode=None, staged_notifications=None):
        memory = Memory(self.domain)
        from koyori.privacy import memory_fence

        privacy = self.store.get("Domain", (hkey(ctx.h), f"PRIVACY#{ctx.actor}"))
        source, checks = memory.source_authority(ctx, body["source"])
        checks.append(memory_fence(memory, ctx))
        if body.get("targetMemoryId"):
            target = memory.get(ctx, body["targetMemoryId"], owner=True)
            if (
                target["rev"] != body["targetRevision"]
                or target["kind"] != body["kind"]
                or target["key"] != body["key"]
            ):
                raise Problem(
                    409,
                    "LEARNING_TARGET_CHANGED",
                    "Correction must name the current memory and key.",
                )
            checks.append(guard("Domain", target))
        identifier = uid()
        item = row(
            hkey(ctx.h),
            f"LEARNING#{identifier}",
            id=identifier,
            owner=ctx.actor,
            status="PROPOSED",
            sourceRevision=source["rev"] if source else None,
            memberEpoch=ctx.member.get("accessEpoch", 1),
            privacyEpoch=(privacy or {}).get("epoch", 0),
            origin=origin,
            mode=mode,
            createdAt=self.domain.now(),
            expiresAt=self.domain.now() + 7 * 86400,
            **body,
        )
        return (
            {"id": identifier, "rev": 1},
            checks
            + [
                put("Domain", item),
                self.domain.event(ctx, identifier, item["rev"], kind="learning"),
            ]
            + Notifications(self.domain).queue(
                ctx, "learning", identifier, "PROPOSED", staged=staged_notifications
            ),
            False,
        )

    def decide(self, ctx, identifier, body, version):
        item = self.get(ctx, identifier)
        self.domain.require_version(item, version)
        if (
            item["status"] != "PROPOSED"
            or item["expiresAt"] <= self.domain.now()
            or item["memberEpoch"] != ctx.member.get("accessEpoch", 1)
        ):
            raise Problem(409, "LEARNING_STALE", "Proposal is no longer eligible for acceptance.")
        checks = []
        result = None
        if body["decision"] == "accept":
            memory = Memory(self.domain)
            fence = self.store.get("Domain", (hkey(ctx.h), f"PRIVACY#{ctx.actor}"))
            if (fence or {}).get("epoch", 0) != item.get("privacyEpoch", 0):
                raise Problem(409, "LEARNING_STALE", "Proposal predates memory erasure.")
            source, checks = memory.source_authority(ctx, item["source"])
            if source and source["rev"] != item["sourceRevision"]:
                raise Problem(
                    409,
                    "LEARNING_SOURCE_CHANGED",
                    "Feedback source has changed; revise the proposal.",
                )
            if item.get("targetMemoryId"):
                patch = MemoryPatch(text=item["text"], steps=item["steps"]).model_dump(
                    exclude_unset=True
                )
                result, writes, _ = memory.change(
                    ctx, item["targetMemoryId"], patch, item["targetRevision"]
                )
            else:
                body = MemoryWrite(
                    kind=item["kind"],
                    text=item["text"],
                    key=item["key"],
                    steps=item["steps"],
                    source=item["source"],
                ).model_dump()
                result, writes, _ = memory.create(ctx, body)
            checks += writes
        new = revised(
            item,
            status="ACCEPTED" if result else "REJECTED",
            memoryId=result["id"] if result else None,
            memoryRevision=result["rev"] if result else None,
        )
        return (
            {"id": identifier, "rev": new["rev"], "memoryId": new["memoryId"]},
            checks
            + [
                put("Domain", new, item),
                self.domain.event(ctx, identifier, new["rev"], kind="learning"),
            ]
            + Notifications(self.domain).queue(ctx, "learning", identifier, new["status"]),
            False,
        )

    def public(self, ctx, identifier):
        item = self.get(ctx, identifier)
        fence_key = (hkey(ctx.h), f"PRIVACY#{ctx.actor}")
        fence = self.store.get("Domain", fence_key)
        if fence and (
            fence["status"] == "ERASING" or fence["epoch"] != item.get("privacyEpoch", 0)
        ):
            raise missing()
        value = projection(item)
        checks = [
            guard("Domain", item),
            guard("Domain", fence) if fence else Change("Domain", fence_key, None),
        ]
        stale = False
        if item.get("targetMemoryId") and not item.get("memoryId"):
            try:
                target = Memory(self.domain).get(ctx, item["targetMemoryId"], owner=True)
                stale = target["rev"] != item["targetRevision"]
                checks.extend(Memory(self.domain).read_checks(ctx, target))
            except Problem as exc:
                if exc.status != 404:
                    raise
                stale = True
        # Erasure of a source or learned memory must not expose its old text through a proposal.
        if item.get("memoryId"):
            try:
                current = Memory(self.domain).get(ctx, item["memoryId"])
                value["text"], value["steps"] = current["text"], current["steps"]
                checks.extend(Memory(self.domain).read_checks(ctx, current))
            except Problem:
                value["text"], value["steps"] = "", []
        elif item["source"]["kind"] != "declaration":
            try:
                source, authority = Memory(self.domain).source_authority(ctx, item["source"])
                stale |= source["rev"] != item["sourceRevision"]
                checks.extend(authority)
            except Problem as exc:
                if exc.status not in {403, 404}:
                    raise
                value["text"], value["steps"] = "", []
        if stale:
            value["text"], value["steps"] = "", []
        value["sourceStatus"] = "changed" if stale else "available" if value["text"] else "absent"
        self.store.transact(ctx.guards() + Memory(self.domain).disclosure_fence() + checks)
        return value
