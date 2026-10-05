"""Sourced, reversible learning proposals. Acceptance changes memory, never permissions."""

from koyori.domain import hkey, projection, row, uid
from koyori.errors import Problem, missing
from koyori.memory import Memory
from koyori.notifications import Notifications
from koyori.stage2 import Service
from koyori.stage2_contracts import MemoryPatch, MemoryWrite
from koyori.store import guard, put, revised


class Learning(Service):
    def get(self, ctx, identifier):
        self.domain.personal(ctx)
        item = self.store.get("Domain", (hkey(ctx.h), f"LEARNING#{identifier}"))
        if not item or item["owner"] != ctx.actor:
            raise missing()
        return item

    def propose(self, ctx, body):
        memory = Memory(self.domain)
        source, checks = memory.source_authority(ctx, body["source"])
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
            + Notifications(self.domain).queue(ctx, "learning", identifier, "PROPOSED"),
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
            source, checks = memory.source_authority(ctx, item["source"])
            if source and source["rev"] != item["sourceRevision"]:
                raise Problem(
                    409,
                    "LEARNING_SOURCE_CHANGED",
                    "Feedback source has changed; revise the proposal.",
                )
            if item.get("targetMemoryId"):
                patch = MemoryPatch(text=item["text"], steps=item["steps"]).model_dump()
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
        value = projection(item)
        # Erasure of a source or learned memory must not expose its old text through a proposal.
        if item.get("memoryId"):
            try:
                current = Memory(self.domain).get(ctx, item["memoryId"])
                value["text"], value["steps"] = current["text"], current["steps"]
            except Problem:
                value["text"], value["steps"] = "", []
        elif item["source"]["kind"] != "declaration":
            try:
                Memory(self.domain).source(ctx, item["source"])
            except Problem:
                value["text"], value["steps"] = "", []
        return value
