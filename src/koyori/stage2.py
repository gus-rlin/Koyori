"""Shared transaction wrapper; idempotency receipts contain identifiers, never memories/tokens."""

from koyori.domain import Domain, row
from koyori.errors import Conflict, Problem
from koyori.security import digest, idempotency_key, request_hash
from koyori.store import put, revised


class Service:
    def __init__(self, domain: Domain):
        self.domain, self.store = domain, domain.store

    def mutate(
        self, ctx, operation, body, key, version, grant, work, authorize=None, protect=False
    ):
        restored = self.store.get("Sessions", ("RESTORE_FENCE", "META"))
        if restored and restored.get("blocked"):
            raise Problem(
                503, "RESTORE_OFFLINE", "Restored namespace awaits operator reconciliation."
            )
        key = idempotency_key(key)
        hashed = request_hash(body, version)
        cache_key = (
            f"IDEMP2#{digest({'p': ctx.actor, 'h': ctx.h, 'op': operation, 'key': key})}",
            "META",
        )
        for _ in range(6):
            fresh = self.domain.context(ctx.actor, ctx.h)
            self.domain.personal(fresh)
            if authorize:
                authorize(fresh)
            cached = self.store.get("Sessions", cache_key)
            if cached:
                if cached["requestHash"] != hashed:
                    raise Problem(409, "IDEMPOTENCY_CONFLICT", "The key has different content.")
                if protect:
                    from koyori.calendar import Envelope

                    return Envelope(self.domain.settings).open(
                        cached["response"], ctx.actor, cache_key[0]
                    )
                return cached["response"]
            response, writes, expands = work(fresh)
            if expands:
                writes.append(self.domain._grant(fresh, grant, operation, hashed))
            cached_response = response
            if protect:
                from koyori.calendar import Envelope

                cached_response = Envelope(self.domain.settings).seal(
                    response, ctx.actor, cache_key[0]
                )
            writes.append(
                put("Sessions", row(*cache_key, requestHash=hashed, response=cached_response))
            )
            try:
                self.store.transact(fresh.guards() + writes)
                return response
            except Conflict:
                continue
        raise Problem(503, "CONTENTION", "Concurrent changes; retry the same key.", True)

    def pending(self, category, limit=20):
        """Bounded shard scans; canonical intents, rather than the queue, drive recovery."""
        items = []
        for shard in range(self.domain.settings.shards):
            page, _ = self.store.query("Delivery", f"{category}#{shard}", index="GSI1", limit=limit)
            items.extend(page)
        return sorted(
            [
                item
                for item in items
                if item.get("dueAt", int(item["GSI1SK"][:20])) <= self.domain.now()
            ],
            key=lambda item: (item.get("dueAt", int(item["GSI1SK"][:20])), item["PK"]),
        )[:limit]

    def defer(self, intent, due):
        delayed = revised(
            intent,
            dueAt=due,
            retries=intent.get("retries", 0) + 1,
            GSI1SK=f"{due:020d}#{intent['GSI1SK'].split('#', 1)[1]}",
        )
        try:
            self.store.transact([put("Delivery", delayed, intent)])
        except Conflict:
            pass  # A newer canonical operation owns scheduling now.
