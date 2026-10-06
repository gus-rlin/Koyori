"""Bounded reconciliation with inbox deduplication, durable intents and fencing.

A queue is a delivery optimization. Pending outbox and run records are the
recoverable authority. A run stores a checkpoint before doing its next step.
"""

import json

from koyori.contracts import Event
from koyori.domain import TERMINAL, Context, Domain, active, hkey, row, uid
from koyori.errors import Conflict, Problem
from koyori.store import guard, put, revised

REPLAY_WINDOW = 14 * 86400


class Engine:
    def __init__(self, domain: Domain):
        self.domain, self.store = domain, domain.store
        self.settings = domain.settings

    def run_key(self, tid: str) -> tuple[str, str]:
        return f"RUN#{tid}", "META"

    def parse(self, raw: dict) -> Event:
        if len(json.dumps(raw).encode()) > 32768:
            raise ValueError("Event too large")
        event = Event.model_validate(raw)
        if event.occurredAt > self.domain.now() + 60:
            raise ValueError("Event timestamp is in the future")
        return event

    def consume(self, raw: dict) -> None:
        event = self.parse(raw)
        inbox_key = (f"INBOX#workflow#{event.eventId}", "META")
        for _ in range(6):
            if self.store.get("Delivery", inbox_key):
                return
            inbox = row(
                *inbox_key,
                receivedAt=self.domain.now(),
                expiresAt=self.domain.now() + 30 * 86400,
                outcome="IGNORED",
            )
            changes = []
            if event.wake and event.type == "koyori.task.changed.v1":
                task = self.store.get(
                    "Domain", (hkey(event.householdId), f"TASK#{event.aggregateId}")
                )
                if (
                    task
                    and task.get("operation") != "coordination.goal"
                    and task["status"] not in TERMINAL | {"PAUSED"}
                ):
                    if event.aggregateVersion > task["rev"]:
                        raise ValueError("Event references a future aggregate revision")
                    intent = self.store.get("Delivery", self.run_key(task["id"]))
                    leased = bool(task["leaseOwner"] and task["leaseUntil"] > self.domain.now())
                    if event.occurredAt >= self.domain.now() - REPLAY_WINDOW:
                        # An in-window wake updates the current aggregate, never an old snapshot.
                        new = revised(task, wakeSeq=task["wakeSeq"] + 1)
                        changes.append(put("Domain", new, task))
                        inbox["outcome"] = "WAKE_RECORDED"
                    else:
                        # After the replay window, restore only a canonical recovery intent.
                        # Do not replay the old wake or reclaim a still-valid lease.
                        new = task
                        changes.append(guard("Domain", task))
                        inbox["outcome"] = "CANONICAL_RECONCILED"
                    if not leased or not intent or intent["status"] != "PENDING":
                        due = task["leaseUntil"] if leased else self.domain.now()
                        changes.append(
                            put("Delivery", self.domain.run_intent(new, intent, due), intent)
                        )
            changes.append(put("Delivery", inbox))
            try:
                self.store.transact(changes)
                return
            except Conflict:
                continue
        raise Conflict("Wake consumer contention")

    def project_activity(self, raw: dict) -> None:
        event = self.parse(raw)
        inbox_key = (f"INBOX#activity#{event.eventId}", "META")
        for _ in range(6):
            if self.store.get("Delivery", inbox_key):
                return
            changes = [
                put(
                    "Delivery",
                    row(
                        *inbox_key,
                        receivedAt=self.domain.now(),
                        expiresAt=self.domain.now() + 30 * 86400,
                    ),
                )
            ]
            household = self.store.get("Domain", (hkey(event.householdId), "META"))
            if household and event.occurredAt >= self.domain.now() - REPLAY_WINDOW:
                changes.append(guard("Domain", household))
                members = [
                    self.store.get("Domain", (hkey(event.householdId), f"MEMBER#{p}"))
                    for p in household["memberIds"]
                ]
                for member in members:
                    if not active(member, self.domain.now()):
                        continue
                    actor = member["principalId"]
                    try:
                        ctx = self.domain.context(actor, event.householdId)
                        if event.type == "koyori.task.changed.v1":
                            _, checks = self.domain.task_access(ctx, event.aggregateId)
                            changes.extend(checks)
                        else:
                            from koyori.object_access import event_access

                            changes.extend(
                                event_access(self.domain, ctx, event.type, event.aggregateId)
                            )
                        changes.extend(ctx.guards())
                    except Problem as exc:
                        if exc.status in {403, 404}:
                            continue
                        raise
                    counter_key = (f"FEED#{event.householdId}#{actor}", "COUNTER")
                    counter = self.store.get("Delivery", counter_key)
                    seq = counter["sequence"] + 1 if counter else 1
                    new_counter = (
                        revised(counter, sequence=seq)
                        if counter
                        else row(*counter_key, sequence=seq)
                    )
                    changes.extend(
                        [
                            put("Delivery", new_counter, counter),
                            put(
                                "Delivery",
                                row(
                                    counter_key[0],
                                    f"SEQ#{seq:020d}",
                                    sequence=seq,
                                    eventId=event.eventId,
                                    type=event.type,
                                    aggregateId=event.aggregateId,
                                    aggregateVersion=event.aggregateVersion,
                                    occurredAt=event.occurredAt,
                                    mode=event.mode,
                                ),
                            ),
                        ]
                    )
                    from koyori.realtime import signal_intent

                    changes.append(signal_intent(self.domain, ctx, seq))
            try:
                self.store.transact(changes)
                return
            except Conflict:
                continue
        raise Conflict("Activity consumer contention")

    def _authority(self, task: dict) -> tuple[Context | None, list, bool]:
        household = self.store.get("Domain", (task["PK"], "META"))
        owner = self.store.get("Domain", (task["PK"], f"MEMBER#{task['owner']}"))
        profile = self.store.get("Domain", (f"P#{task['owner']}", "PROFILE"))
        policy = self.store.get("Domain", (task["PK"], "POLICY#synthetic"))
        ctx = (
            Context(task["owner"], household, owner, profile)
            if household and owner and profile
            else None
        )
        checks = [guard("Domain", r) for r in (household, owner, profile, policy) if r]
        allowed = bool(
            ctx
            and active(owner, self.domain.now())
            and active(profile, self.domain.now())
            and profile["kind"] == "personal"
            and task["executionAuthorized"]
            and task.get("grantEpoch", 1) == owner.get("accessEpoch", 1)
            and policy
            and policy["enabled"]
        )
        return ctx, checks, allowed

    def acquire(self, h: str, tid: str, owner: str | None = None) -> dict | None:
        owner = owner or uid()
        for _ in range(6):
            task = self.store.get("Domain", (hkey(h), f"TASK#{tid}"))
            intent = self.store.get("Delivery", self.run_key(tid))
            if (
                not task
                or task.get("operation") == "coordination.goal"
                or not intent
                or intent["status"] != "PENDING"
                or intent["dueAt"] > self.domain.now()
            ):
                return None
            if task["status"] in TERMINAL:
                try:
                    self.store.transact(
                        [
                            guard("Domain", task),
                            put("Delivery", self.domain.done_intent(intent), intent),
                        ]
                    )
                    return None
                except Conflict:
                    continue
            if task["leaseOwner"] and task["leaseUntil"] > self.domain.now():
                return None
            ctx, checks, allowed = self._authority(task)
            if not allowed:
                if not ctx:
                    raise ValueError("Task authority records missing")
                new = revised(
                    task,
                    status="FAILED",
                    result={"kind": "synthetic", "code": "AUTHORITY_REVOKED"},
                    leaseOwner=None,
                    leaseUntil=0,
                    runEpoch=task["runEpoch"] + 1,
                    updatedAt=self.domain.now(),
                )
                changes = checks + [
                    put("Domain", new, task),
                    put(
                        "Domain",
                        revised(ctx.household, activeTasks=ctx.household["activeTasks"] - 1),
                        ctx.household,
                    ),
                    put("Delivery", self.domain.done_intent(intent), intent),
                    self.domain.event(ctx, tid, new["rev"]),
                ]
            elif task["status"] == "PAUSED":
                # Keep checking authority without acquiring a lease or advancing checkpoints.
                new = None
                changes = checks + [
                    guard("Domain", task),
                    put(
                        "Delivery",
                        self.domain.run_intent(
                            task, intent, self.domain.now() + self.settings.lease_seconds
                        ),
                        intent,
                    ),
                ]
            else:
                new = revised(
                    task,
                    status="RUNNING",
                    runEpoch=task["runEpoch"] + 1,
                    leaseOwner=owner,
                    leaseUntil=self.domain.now() + self.settings.lease_seconds,
                    runWake=task["wakeSeq"],
                    updatedAt=self.domain.now(),
                )
                changes = checks + [
                    put("Domain", new, task),
                    put("Delivery", self.domain.run_intent(new, intent, new["leaseUntil"]), intent),
                    self.domain.event(ctx, tid, new["rev"]),
                ]
            try:
                self.store.transact(changes)
                return new if allowed else None
            except Conflict:
                continue
        raise Conflict("Run acquisition contention")

    def advance(self, snapshot: dict, *, release: bool = False) -> dict | None:
        """One fenced checkpoint. A wake only updates wakeSeq; it does not invalidate the lease."""
        for _ in range(6):
            task = self.store.get("Domain", (snapshot["PK"], snapshot["SK"]))
            if (
                not task
                or (task["runEpoch"], task["leaseOwner"])
                != (snapshot["runEpoch"], snapshot["leaseOwner"])
                or task["leaseUntil"] <= self.domain.now()
                or task["status"] != "RUNNING"
            ):
                return None
            # Only wake receipts may have changed the revision since this worker's
            # snapshot. A repeated/stale checkpoint must never advance a second step.
            if task["rev"] != snapshot["rev"] and (
                task["checkpoint"] != snapshot["checkpoint"]
                or task["rev"] - snapshot["rev"] != task["wakeSeq"] - snapshot["wakeSeq"]
            ):
                return None
            ctx, checks, allowed = self._authority(task)
            if not ctx:
                raise ValueError("Task authority records missing")
            intent = self.store.get("Delivery", self.run_key(task["id"]))
            if not intent:
                raise ValueError("Run recovery intent missing")
            values = dict(updatedAt=self.domain.now())
            terminal = False
            if not allowed:
                values.update(
                    status="FAILED", result={"kind": "synthetic", "code": "AUTHORITY_REVOKED"}
                )
                terminal = True
            elif release:
                values.update(status="READY", handledWake=task["runWake"])
            elif task["checkpoint"] < 2:
                values.update(
                    checkpoint=task["checkpoint"] + 1,
                    leaseUntil=self.domain.now() + self.settings.lease_seconds,
                )
            elif task["wakeSeq"] > task["runWake"]:
                # Reconcile a newly arrived wake in a separate finite run before completing.
                values.update(status="READY", handledWake=task["runWake"])
            else:
                values.update(
                    status="SUCCEEDED",
                    handledWake=task["runWake"],
                    result={
                        "kind": "synthetic",
                        "code": "CHECKPOINT_CONFIRMED",
                        "markers": ["checkpoint-1", "checkpoint-2"],
                    },
                )
                terminal = True
            if terminal or values.get("status") == "READY":
                values.update(leaseOwner=None, leaseUntil=0)
            new = revised(task, **values)
            writes = checks + [
                put("Domain", new, task),
                self.domain.event(ctx, task["id"], new["rev"]),
            ]
            if terminal:
                writes.extend(
                    [
                        put(
                            "Domain",
                            revised(ctx.household, activeTasks=ctx.household["activeTasks"] - 1),
                            ctx.household,
                        ),
                        put("Delivery", self.domain.done_intent(intent), intent),
                    ]
                )
            else:
                writes.append(
                    put(
                        "Delivery",
                        self.domain.run_intent(
                            new,
                            intent,
                            self.domain.now() if new["status"] == "READY" else new["leaseUntil"],
                        ),
                        intent,
                    )
                )
            try:
                self.store.transact(writes)
                return new
            except Conflict:
                continue
        raise Conflict("Checkpoint contention")

    def run(self, h: str, tid: str) -> None:
        snapshot = self.acquire(h, tid)
        for _ in range(3):
            if not snapshot or snapshot["status"] != "RUNNING":
                return
            snapshot = self.advance(snapshot)

    def pending(self, kind: str, *, budget: int = 100) -> list[dict]:
        """Indexes discover candidates only; the base row always decides their current state."""
        result = []
        per_shard = max(1, budget // self.settings.shards)
        for shard in range(self.settings.shards):
            # Reserve capacity for every shard; a busy/future shard cannot starve
            # ready work elsewhere. Later sweeps progress as pending rows leave the index.
            records, _ = self.store.query(
                "Delivery", f"{kind}#{shard}", index="GSI1", limit=min(50, per_shard)
            )
            for candidate in records:
                item = self.store.get("Delivery", (candidate["PK"], candidate["SK"]))
                if item and item["status"] == "PENDING":
                    result.append(item)
        return result

    def repair(self) -> int:
        count = 0
        for intent in self.pending("RUN"):
            if intent["dueAt"] <= self.domain.now():
                self.run(intent["h"], intent["taskId"])
                count += 1
        return count


class Publisher:
    def __init__(self, engine: Engine):
        self.engine, self.settings = engine, engine.settings
        self.sqs = self.settings.client("sqs") if self.settings.env == "local" else None
        self.events = self.settings.client("events") if self.settings.env != "local" else None

    def send(self, envelope: dict) -> None:
        body = json.dumps(envelope, separators=(",", ":"))
        if self.sqs:
            for url in (self.settings.workflow_url, self.settings.activity_url):
                if not url:
                    raise ValueError("Queue URL missing")
                self.sqs.send_message(QueueUrl=url, MessageBody=body)
        else:
            response = self.events.put_events(
                Entries=[
                    dict(
                        Source="koyori.control",
                        DetailType=envelope["type"],
                        Detail=body,
                        EventBusName=self.settings.bus_name,
                    )
                ]
            )
            if response.get("FailedEntryCount") or not response["Entries"][0].get("EventId"):
                raise RuntimeError("Event publication not acknowledged")

    def publish_one(self, record: dict, *, fail_after_send: bool = False) -> None:
        item = self.engine.store.get("Delivery", (record["PK"], record["SK"]))
        if not item or item["status"] != "PENDING":
            return
        self.send(item["envelope"])
        if fail_after_send:
            raise RuntimeError("Injected crash after publication")
        new = revised(item, status="SENT", sentAt=self.engine.domain.now())
        new.pop("GSI1PK", None)
        new.pop("GSI1SK", None)
        try:
            self.engine.store.transact([put("Delivery", new, item)])
        except Conflict:
            pass  # Another publisher has already acknowledged; duplicates are safe.

    def sweep(self) -> int:
        records = self.engine.pending("OUTBOX")
        for item in records:
            self.publish_one(item)
        return len(records)
