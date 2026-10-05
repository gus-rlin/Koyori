"""Grouped, quiet-hour notification intents. Reads reauthorize their underlying objects."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from koyori.domain import hkey, row
from koyori.errors import Conflict, Problem
from koyori.scheduling import civil_timestamp
from koyori.security import digest
from koyori.stage2 import Service
from koyori.stage3_contracts import NotificationPolicy
from koyori.store import guard, put, revised


def delivery_time(now, policy):
    zone = ZoneInfo(policy["timeZone"])
    local = datetime.fromtimestamp(now, zone)
    clock = local.strftime("%H:%M")
    start, end = policy["quietStart"], policy["quietEnd"]
    quiet = (
        start <= clock < end
        if start < end
        else (clock >= start or clock < end)
        if start > end
        else False
    )
    if not quiet:
        return now
    day = local.date() + timedelta(days=int(start > end and clock >= start))
    # Quiet-end in a DST gap advances to the next valid minute, never into the quiet period.
    for offset in range(181):
        naive = datetime.combine(day, datetime.min.time()).replace(
            hour=int(end[:2]), minute=int(end[3:])
        ) + timedelta(minutes=offset)
        due = civil_timestamp(
            naive.date(), naive.strftime("%H:%M"), policy["timeZone"], ambiguous="second"
        )
        if due is not None and due >= now:
            return due
    raise Problem(422, "INVALID_QUIET_HOURS", "Quiet-hour end cannot be normalized.")


class Notifications(Service):
    def policy(self, ctx):
        return self.store.get("Domain", (hkey(ctx.h), f"NOTIFY_POLICY#{ctx.actor}"))

    def configure(self, ctx, body, version):
        old = self.policy(ctx)
        self.domain.require_version(old, version)
        item = (
            row(hkey(ctx.h), f"NOTIFY_POLICY#{ctx.actor}", owner=ctx.actor, **body)
            if not old
            else revised(old, **body)
        )
        return {"rev": item["rev"]}, [put("Domain", item, old)], False

    def queue(self, ctx, kind, identifier, status):
        policy = self.policy(ctx)
        settings = policy or NotificationPolicy(timeZone=ctx.household["timeZone"]).model_dump()
        group = settings["groupSeconds"]
        bucket = self.domain.now() // max(1, group)
        for chunk in range(64):
            nid = digest({"h": ctx.h, "p": ctx.actor, "bucket": bucket, "chunk": chunk})[:32]
            key = (f"NOTIFY#{ctx.h}#{ctx.actor}", f"BATCH#{nid}")
            old = self.store.get("Delivery", key)
            entries = list(old["entries"]) if old else []
            if len(entries) < 16 or any(
                (e["kind"], e["id"]) == (kind, identifier) for e in entries
            ):
                break
        else:
            raise Problem(429, "NOTIFICATION_LIMIT", "Notification grouping ceiling reached.")
        entry = {"kind": kind, "id": identifier, "status": status}
        entries = [e for e in entries if (e["kind"], e["id"]) != (kind, identifier)]
        entries.append(entry)
        due = delivery_time(self.domain.now() + group, settings)
        item = row(
            *key,
            rev=old["rev"] + 1 if old else 1,
            id=nid,
            h=ctx.h,
            owner=ctx.actor,
            memberEpoch=ctx.member.get("accessEpoch", 1),
            entries=entries,
            status="PENDING",
            dueAt=due,
            GSI1PK=f"NOTIFYRUN#{int(nid[:8], 16) % self.domain.settings.shards}",
            GSI1SK=f"{due:020d}#{nid}",
        )
        writes = [put("Delivery", item, old)]
        if policy:
            writes.append(guard("Domain", policy))
        return writes

    def entries(self, ctx, item):
        if (
            ctx.profile["kind"] != "personal"
            or item["owner"] != ctx.actor
            or item["memberEpoch"] != ctx.member.get("accessEpoch", 1)
        ):
            return []
        values = []
        for entry in item["entries"]:
            try:
                if entry["kind"] == "goal":
                    from koyori.goals import Goals

                    obj = Goals(self.domain).get(ctx, entry["id"])
                    values.append({"kind": "goal", "id": obj["id"], "status": obj["status"]})
                else:
                    from koyori.learning import Learning

                    obj = Learning(self.domain).get(ctx, entry["id"])
                    values.append({"kind": "learning", "id": obj["id"], "status": obj["status"]})
            except Problem as exc:
                if exc.status not in {403, 404}:
                    raise
        return values

    def list(self, ctx, cursor=None):
        self.domain.personal(ctx)

        def authorize(item):
            if item["status"] != "DELIVERED":
                return None
            entries = self.entries(ctx, item)
            return (
                {"id": item["id"], "deliveredAt": item["deliveredAt"], "entries": entries}
                if entries
                else None
            )

        return self.domain.page(
            ctx,
            "Delivery",
            "BATCH#",
            "notifications",
            cursor,
            pk=f"NOTIFY#{ctx.h}#{ctx.actor}",
            authorize=authorize,
        )

    def sweep(self):
        attempts = 0
        for candidate in self.pending("NOTIFYRUN"):
            item = self.store.get("Delivery", (candidate["PK"], candidate["SK"]))
            if not item or item["status"] != "PENDING" or item["dueAt"] > self.domain.now():
                continue
            attempts += 1
            try:
                ctx = self.domain.context(item["owner"], item["h"])
                policy = self.policy(ctx)
                settings = (
                    policy or NotificationPolicy(timeZone=ctx.household["timeZone"]).model_dump()
                )
                due = delivery_time(self.domain.now(), settings)
                if due > self.domain.now():
                    new = revised(item, dueAt=due, GSI1SK=f"{due:020d}#{item['id']}")
                else:
                    new = self.domain.done_intent(item)
                    new.update(
                        status="DELIVERED" if self.entries(ctx, item) else "SUPPRESSED",
                        deliveredAt=self.domain.now(),
                    )
                self.store.transact(
                    ctx.guards()
                    + ([guard("Domain", policy)] if policy else [])
                    + [put("Delivery", new, item)]
                )
            except Conflict:
                continue
            except Problem as exc:
                if exc.status not in {403, 404}:
                    raise
                self.store.transact([put("Delivery", self.domain.done_intent(item), item)])
        return attempts
