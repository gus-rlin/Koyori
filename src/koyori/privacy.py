"""Paginated personal export and resumable erasure; financial evidence remains canonical."""

from koyori.domain import hkey, projection, row, uid
from koyori.errors import Conflict, Problem, missing
from koyori.memory import Memory
from koyori.stage2 import Service
from koyori.store import guard, put, revised


class Privacy(Service):
    def export(self, ctx, cursor=None):
        self.domain.personal(ctx)
        after = self.domain.cursors.decode(cursor, ctx.actor, ctx.h, "personal-export")
        records, last = self.store.query("Domain", hkey(ctx.h), after=after, limit=20)
        allowed = ("MEMORY#", "TASK#", "ACTION#", "CONNECTION#", "ROUTINE#", "LEARNING#")
        items, checks = [], []
        for item in records:
            if (
                item.get("owner") != ctx.actor
                or not item["SK"].startswith(allowed)
                or item.get("deleted")
            ):
                continue
            value = projection(item)
            if item["SK"].startswith("MEMORY#"):
                try:
                    memory = Memory(self.domain)
                    current = memory.get(ctx, item["id"], owner=True)
                    value = projection(current)
                    checks.extend(memory.read_checks(ctx, current))
                except Problem as exc:
                    if exc.status == 404:
                        continue
                    raise
            for key in (
                "providerKey",
                "intents",
                "leaseUntil",
                "memberEpoch",
                "runEpoch",
                "grantEpoch",
                "dispatchEpoch",
                "credentials",
                "watchToken",
            ):
                value.pop(key, None)
            items.append({"kind": item["SK"].split("#", 1)[0].lower(), "data": value})
            checks.append(guard("Domain", item))
        self.store.transact(ctx.guards() + checks)
        return {
            "schemaVersion": "1.0",
            "items": items,
            "nextCursor": self.domain.cursors.encode(ctx.actor, ctx.h, "personal-export", last)
            if last
            else None,
            "scope": "owned-household-data",
            "excludes": ["credentials", "other-members", "transient-grants"],
            "retention": "Commercial evidence is retained separately from erased memories.",
        }

    def start(self, ctx):
        fence = self.store.get("Domain", (hkey(ctx.h), f"PRIVACY#{ctx.actor}"))
        if fence and fence["status"] == "ERASING":
            return {"id": fence["jobId"]}, [], True
        identifier = uid()
        job = row(
            hkey(ctx.h),
            f"ERASURE#{identifier}",
            id=identifier,
            owner=ctx.actor,
            status="PENDING",
            after=None,
            erased=0,
            createdAt=self.domain.now(),
        )
        updated = row(
            hkey(ctx.h),
            f"PRIVACY#{ctx.actor}",
            rev=(fence or {}).get("rev", 0) + 1,
            owner=ctx.actor,
            status="ERASING",
            jobId=identifier,
            epoch=(fence or {}).get("epoch", 0) + 1,
        )
        intent = row(
            f"ERASERUN#{identifier}",
            h=ctx.h,
            jobId=identifier,
            status="PENDING",
            GSI1PK=f"ERASERUN#{int(identifier[:8], 16) % self.domain.settings.shards}",
            GSI1SK=f"{self.domain.now():020d}#{identifier}",
        )
        return (
            {"id": identifier},
            [put("Domain", job), put("Domain", updated, fence), put("Delivery", intent)],
            True,
        )

    def get(self, ctx, identifier):
        self.domain.personal(ctx)
        item = self.store.get("Domain", (hkey(ctx.h), f"ERASURE#{identifier}"))
        if not item or item["owner"] != ctx.actor:
            raise missing()
        return projection(item)

    def sweep(self):
        for candidate in self.pending("ERASERUN"):
            for _ in range(6):
                intent = self.store.get("Delivery", (candidate["PK"], "META"))
                job = self.store.get("Domain", (hkey(intent["h"]), f"ERASURE#{intent['jobId']}"))
                if intent["status"] != "PENDING":
                    break
                # Erasure is still owed after access revocation; never read user text for logs.
                owner = self.store.get("Domain", (hkey(intent["h"]), f"MEMBER#{job['owner']}"))
                profile = self.store.get("Domain", (f"P#{job['owner']}", "PROFILE"))
                household = self.store.get("Domain", (hkey(intent["h"]), "META"))
                from koyori.domain import Context

                ctx = Context(job["owner"], household, owner, profile)
                records, last = self.store.query(
                    "Domain", hkey(ctx.h), prefix="MEMORY#", after=job["after"], limit=8
                )
                writes, erased = [], job["erased"]
                for item in records:
                    if item["owner"] == ctx.actor and not item["deleted"]:
                        _, changes, _ = Memory(self.domain).change(
                            ctx, item["id"], {}, item["rev"], delete=True
                        )
                        writes.extend(changes)
                        erased += 1
                writes.append(
                    put(
                        "Domain",
                        revised(
                            job,
                            after=last,
                            erased=erased,
                            status="RUNNING" if last else "COMPLETED",
                            completedAt=None if last else self.domain.now(),
                        ),
                        job,
                    )
                )
                if not last:
                    fence = self.store.get("Domain", (hkey(ctx.h), f"PRIVACY#{ctx.actor}"))
                    writes.extend(
                        [
                            put("Domain", revised(fence, status="COMPLETE"), fence),
                            put("Delivery", self.domain.done_intent(intent), intent),
                        ]
                    )
                else:
                    writes.append(guard("Delivery", intent))
                try:
                    self.store.transact(writes)
                    break
                except Conflict:
                    continue
            else:
                raise Conflict("Erasure contention")


def memory_fence(memory, ctx):
    fence = memory.store.get("Domain", (hkey(ctx.h), f"PRIVACY#{ctx.actor}"))
    if fence and fence["status"] == "ERASING":
        raise Problem(409, "MEMORY_ERASING", "Memory erasure is in progress.")
    # Guard absence too: a simultaneous start must defeat a prepared memory write.
    from koyori.store import Change

    return (
        guard("Domain", fence)
        if fence
        else Change("Domain", (hkey(ctx.h), f"PRIVACY#{ctx.actor}"), None)
    )
