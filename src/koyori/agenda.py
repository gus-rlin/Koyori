"""Calendar event proposals, confirmed by their owner, then created once at Google.

Anyone may propose (the person or the assistant); only the person's explicit
decision admits a write. The provider event id derives from the proposal, so a
lost response or a retried sweep finds the existing event instead of duplicating it.
"""

import hashlib
import json
import logging
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from koyori.calendar import Calendar
from koyori.domain import Context, active, hkey, projection, row, uid
from koyori.errors import Conflict, Problem, missing
from koyori.security import digest
from koyori.stage2 import Service
from koyori.store import guard, put, revised

HORIZON = 366 * 86400


class Agenda(Service):
    def __init__(self, domain, calendar=None):
        super().__init__(domain)
        self.calendar = calendar or Calendar(domain)

    def connections(self, ctx):
        rows, _ = self.store.query("Domain", hkey(ctx.h), prefix="CONNECTION#", limit=50)
        return [
            c
            for c in rows
            if c["owner"] == ctx.actor
            and c["provider"] == "google-calendar"
            and active(c, self.domain.now())
        ]

    def writable(self, ctx, cid):
        if cid is None:
            accounts = self.connections(ctx)
            candidates = [c for c in accounts if "calendar.write" in c["capabilities"]] or accounts
            if len(candidates) != 1:
                raise Problem(
                    409, "CALENDAR_ACCOUNT_REQUIRED", "Choose the calendar account to write to."
                )
            cid = candidates[0]["id"]
        connection = self.calendar.get(ctx, cid)
        if not active(connection, self.domain.now()):
            raise Problem(409, "CONNECTION_REVOKED", "Connection is unavailable.")
        if "calendar.write" not in connection["capabilities"]:
            raise Problem(
                409, "CALENDAR_READ_ONLY", "Reconnect the account to allow adding events."
            )
        return connection

    def get(self, ctx, pid):
        item = self.store.get("Domain", (hkey(ctx.h), f"CALPROPOSAL#{pid}"))
        if not item or ctx.profile["kind"] != "personal" or item["owner"] != ctx.actor:
            raise missing()
        return item

    def propose(self, ctx, body, origin):
        connection = self.writable(ctx, body["connectionId"])
        calendar_id = (
            body["calendarId"] or connection.get("account") or connection["calendarIds"][0]
        )
        if calendar_id not in connection["calendarIds"]:
            raise Problem(422, "CALENDAR_NOT_SELECTED", "Calendar is not part of this connection.")
        now = self.domain.now()
        if body["endAt"] <= now or body["startAt"] > now + HORIZON:
            raise Problem(422, "INVALID_EVENT_TIME", "Event must end in the future, within a year.")
        pid = uid()
        item = row(
            hkey(ctx.h),
            f"CALPROPOSAL#{pid}",
            id=pid,
            owner=ctx.actor,
            origin=origin,
            connectionId=connection["id"],
            calendarId=calendar_id,
            title=body["title"],
            startAt=body["startAt"],
            endAt=body["endAt"],
            location=body["location"],
            notes=body["notes"],
            status="PENDING",
            createdAt=now,
            eventId=None,
            link=None,
            error=None,
        )
        return (
            projection(item),
            [
                guard("Domain", connection),
                put("Domain", item),
                self.domain.event(ctx, pid, 1, kind="calendar", mode="real"),
            ],
            False,
        )

    def decide(self, ctx, pid, version, decision):
        item = self.get(ctx, pid)
        if item["rev"] != version:
            raise Problem(412, "REVISION_CONFLICT", "The resource revision has changed.")
        if item["status"] != "PENDING":
            raise Problem(409, "PROPOSAL_DECIDED", "This proposal was already decided.")
        now = self.domain.now()
        if decision == "reject":
            updated = revised(item, status="REJECTED", decidedAt=now)
            writes = [put("Domain", updated, item)]
        else:
            connection = self.writable(ctx, item["connectionId"])
            updated = revised(item, status="APPROVED", decidedAt=now)
            writes = [
                guard("Domain", connection),
                put("Domain", updated, item),
                put(
                    "Delivery",
                    row(
                        f"CALWRITE#{pid}",
                        h=ctx.h,
                        proposalId=pid,
                        dueAt=now,
                        status="PENDING",
                        GSI1PK=f"CALWRITE#{int(pid[:8], 16) % self.domain.settings.shards}",
                        GSI1SK=f"{now:020d}#{pid}",
                    ),
                ),
            ]
        writes.append(self.domain.event(ctx, pid, updated["rev"], kind="calendar", mode="real"))
        return projection(updated), writes, False

    def sweep(self):
        items = self.pending("CALWRITE")
        for intent in items:
            try:
                self.execute(intent)
            except Conflict:
                continue
            except Problem as exc:
                if exc.retryable:
                    self.retry(intent, exc.code)
                    continue
                try:
                    self.finish(intent, status="FAILED", error=exc.code)
                except Conflict:
                    continue  # The next sweep re-reads the proposal and decides again.
            except Exception:
                self.retry(intent, "DEPENDENCY_UNAVAILABLE")
        return len(items)

    def retry(self, intent, code):
        logging.getLogger("koyori.agenda").warning(
            json.dumps({"event": "calendar_write_retry", "code": code})
        )
        self.defer(
            intent, self.domain.now() + min(3600, 30 * 2 ** min(intent.get("retries", 0), 7))
        )

    def execute(self, intent):
        item = self.store.get("Domain", (hkey(intent["h"]), f"CALPROPOSAL#{intent['proposalId']}"))
        if not item or item["status"] != "APPROVED":
            self.store.transact([put("Delivery", self.domain.done_intent(intent), intent)])
            return
        ctx = self.domain.context(item["owner"], intent["h"])
        connection = self.writable(ctx, item["connectionId"])
        token = self.calendar.access_token(ctx, connection)
        owned = {
            c["id"] for c in self.calendar.google.calendars(token) if c.get("accessRole") == "owner"
        }
        if item["calendarId"] not in owned:
            raise Problem(409, "CALENDAR_NOT_WRITABLE", "Koyori can only add to calendars you own.")
        # Hex digits are valid base32hex, the alphabet Google requires for client ids.
        event_id = hashlib.sha256(item["id"].encode()).hexdigest()
        created = self.calendar.google.event(
            token, item["calendarId"], event_id
        ) or self.calendar.google.insert(
            token, item["calendarId"], self.provider_event(ctx, item, event_id)
        )
        link = created.get("htmlLink")
        sync = self.store.get("Delivery", (f"CALRUN#{connection['id']}", "META"))
        self.finish(
            intent,
            status="CREATED",
            eventId=event_id,
            link=link if isinstance(link, str) and link.startswith("https://") else None,
            extra=[
                guard("Domain", connection),
                # Wake the connection sync so the agenda shows the new event promptly.
                put("Delivery", self.calendar.intent(connection, sync), sync),
            ],
        )

    def provider_event(self, ctx, item, event_id):
        zone = ctx.profile.get("timeZone", ctx.household["timeZone"])

        def moment(seconds):
            return {
                "dateTime": datetime.fromtimestamp(seconds, ZoneInfo(zone)).isoformat(),
                "timeZone": zone,
            }

        event = {
            "id": event_id,
            "summary": item["title"],
            "start": moment(item["startAt"]),
            "end": moment(item["endAt"]),
        }
        if item["location"]:
            event["location"] = item["location"]
        if item["notes"]:
            event["description"] = item["notes"]
        return event

    def finish(self, intent, *, status, extra=(), **values):
        item = self.store.get("Domain", (hkey(intent["h"]), f"CALPROPOSAL#{intent['proposalId']}"))
        updated = revised(item, status=status, **values)
        # The outcome is recorded even if the owner lost access; the event only names them.
        owner = Context(item["owner"], {"id": intent["h"]}, {}, {})
        self.store.transact(
            [
                *extra,
                put("Domain", updated, item),
                put("Delivery", self.domain.done_intent(intent), intent),
                self.domain.event(owner, item["id"], updated["rev"], kind="calendar", mode="real"),
            ]
        )

    def upcoming(self, ctx, start, end):
        if not 0 < end - start <= 31 * 86400:
            raise Problem(422, "INVALID_WINDOW", "Agenda window is limited to 31 days.")
        zone = ZoneInfo(ctx.profile.get("timeZone", ctx.household["timeZone"]))
        items, synced, seen, truncated = [], [], set(), False
        for connection in self.connections(ctx):
            completed = {}
            for calendar_id in connection["calendarIds"]:
                state = self.store.get(
                    "Domain",
                    (
                        connection["PK"],
                        f"CALSYNC#{connection['id']}#{digest({'calendar': calendar_id})}",
                    ),
                )
                if state and state.get("completedGeneration"):
                    completed[calendar_id] = state["completedGeneration"]
                    synced.append(state.get("lastSyncedAt"))
            after = None
            for _ in range(40):
                rows, after = self.store.query(
                    "Domain",
                    connection["PK"],
                    prefix=f"CALEVENT#{connection['id']}#",
                    after=after,
                    limit=50,
                )
                for event in rows:
                    if (
                        event["deleted"]
                        or completed.get(event["calendarId"]) != event["generation"]
                    ):
                        continue
                    begins, all_day = _instant(event.get("start"), zone)
                    finishes, _ = _instant(event.get("end"), zone)
                    if (
                        begins is None
                        or finishes is None
                        or not (begins < end and finishes > start)
                    ):
                        continue
                    # A reconnected account may sync the same calendar under two connections.
                    if (event["calendarId"], event["id"]) in seen:
                        continue
                    seen.add((event["calendarId"], event["id"]))
                    items.append(
                        {
                            "id": event["id"],
                            "connectionId": connection["id"],
                            "calendarId": event["calendarId"],
                            "title": event["summary"],
                            "startAt": begins,
                            "endAt": finishes,
                            "allDay": all_day,
                        }
                    )
                if not after:
                    break
            else:
                # Rows follow key order, not dates: an unscanned page may hold upcoming events.
                truncated = True
        items.sort(key=lambda e: (e["startAt"], e["title"]))
        return {
            "items": items[:200],
            "truncated": truncated or len(items) > 200,
            "syncedAt": min((s for s in synced if s), default=None),
            "mode": "real",
            "source": "google-calendar",
        }


def _instant(value, zone):
    """Google gives timed events an offset dateTime and all-day events a civil date."""
    if not isinstance(value, dict):
        return None, False
    try:
        if "dateTime" in value:
            moment = datetime.fromisoformat(value["dateTime"])
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=UTC)
            return int(moment.timestamp()), False
        if "date" in value:
            day = date.fromisoformat(value["date"])
            return int(datetime.combine(day, time(), zone).timestamp()), True
    except (TypeError, ValueError):
        pass
    return None, False
