"""Finite, fenced coordination runs over the canonical task and stage-two action ledger."""

import copy
import json
from concurrent.futures import ThreadPoolExecutor

from pydantic import ValidationError

from koyori.actions import Actions
from koyori.calendar import Calendar
from koyori.domain import TERMINAL, active, hkey, projection, row, uid
from koyori.errors import Conflict, Problem, missing
from koyori.memory import Memory
from koyori.planner import CallQuota, metadata, planner
from koyori.plans import validate_plan
from koyori.security import digest
from koyori.stage2 import Service
from koyori.stage2_contracts import ContextQuery, QuoteCreate
from koyori.stage3_contracts import SpecialistResult
from koyori.store import guard, put, revised, unique

PENDING_ACTIONS = {"READY", "DISPATCHING", "UNKNOWN"}
RUN_SECONDS = 120
MAX_PLAN_SOURCES = 24


def calendar_checks(domain, h, cid):
    connection = domain.store.get("Domain", (hkey(h), f"CONNECTION#{cid}"))
    if not connection or not active(connection, domain.now()):
        raise Problem(409, "PLAN_CONTEXT_CHANGED", "Calendar authority changed.")
    checks = [guard("Domain", connection)]
    for calendar_id in connection["calendarIds"]:
        state = domain.store.get(
            "Domain", (hkey(h), f"CALSYNC#{cid}#{digest({'calendar': calendar_id})}")
        )
        if not state or not state["complete"]:
            raise Problem(
                409, "CALENDAR_NOT_SYNCHRONIZED", "Wait for complete calendar synchronization."
            )
        checks.append(guard("Domain", state))
    return checks


def calendar_snapshot(calendar, ctx, cid):
    version = calendar.store.get("Domain", (hkey(ctx.h), f"CALVERSION#{cid}"))
    if not version:
        raise Problem(409, "CALENDAR_NOT_SYNCHRONIZED", "Synchronize the calendar first.")
    calendar_checks(calendar.domain, ctx.h, cid)
    page = calendar.events(ctx, cid)
    calendar_checks(calendar.domain, ctx.h, cid)
    items = [
        {"id": e.get("id"), "summary": e.get("summary", "")[:300], "start": e.get("start")}
        for e in page["items"][:8]
    ]
    return {
        "evidence": "calendar_snapshot",
        "connectionId": cid,
        "snapshotRevision": version["rev"],
        "items": items,
        "nextCursor": page.get("nextCursor"),
        "mode": page.get("mode", "real"),
    }


def validate_goal_sources(domain, ctx, task):
    checks = []
    for reference in task.get("planContext", []):
        if reference["kind"] == "memory":
            item = Memory(domain).get(ctx, reference["id"])
            if item["rev"] != reference["revision"]:
                raise Problem(409, "PLAN_CONTEXT_CHANGED", "Canonical plan source changed.")
            checks.append(guard("Domain", item))
        else:
            prefix = "CALVERSION" if reference["kind"] == "calendar" else "CONNECTION"
            item = domain.store.get("Domain", (task["PK"], f"{prefix}#{reference['id']}"))
            if not item or item["rev"] != reference["revision"] or not active(item, domain.now()):
                raise Problem(409, "PLAN_CONTEXT_CHANGED", "Canonical plan source changed.")
            checks.append(guard("Domain", item))
            if reference["kind"] == "calendar":
                checks += calendar_checks(domain, ctx.h, reference["id"])
    if task.get("occurrence"):
        rule = domain.store.get("Domain", (task["PK"], f"ROUTINE#{task['occurrence']['ruleId']}"))
        if not rule or rule["paused"] or rule["ruleVersion"] != task["occurrence"]["ruleVersion"]:
            raise Problem(409, "ROUTINE_CHANGED", "Routine no longer authorizes this occurrence.")
        checks.append(guard("Domain", rule))
    return checks


class Goals(Service):
    def __init__(self, domain, *, planning=None, calendar=None, actions=None):
        super().__init__(domain)
        self.planning = planning
        self.calendar = calendar or Calendar(domain)
        self.actions = actions or Actions(domain)

    def get(self, ctx, tid):
        self.domain.personal(ctx)
        task, _ = self.domain.task_access(ctx, tid, "owner")
        if task.get("operation") != "coordination.goal":
            raise missing()
        return task

    def public(self, ctx, tid):
        task = self.get(ctx, tid)
        value = projection(task)
        for key in ("intents", "grantEpoch", "dispatchEpoch", "handledWake", "quotaActive"):
            value.pop(key, None)
        value["actions"] = [
            self.actions.public(ctx, "ACTION", aid)
            for intent in task["intents"].values()
            for aid in intent["actions"]
        ]
        return value

    def intent(self, task, old=None, due=None):
        due = self.domain.now() if due is None else due
        return row(
            f"GOALRUN#{task['id']}",
            rev=old["rev"] + 1 if old else 1,
            h=task["PK"][2:],
            taskId=task["id"],
            status="PENDING",
            dueAt=due,
            GSI1PK=f"GOALRUN#{int(task['id'][:8], 16) % self.domain.settings.shards}",
            GSI1SK=f"{due:020d}#{task['id']}",
        )

    def create(self, ctx, body, *, task_id=None, occurrence=None):
        self.domain.personal(ctx)
        if ctx.household["activeTasks"] >= self.domain.settings.max_tasks:
            raise Problem(409, "TASK_LIMIT", "Household active task ceiling reached.")
        tid = task_id or uid()
        task = row(
            hkey(ctx.h),
            f"TASK#{tid}",
            id=tid,
            owner=ctx.actor,
            visibility="private",
            label=body["text"][:200],
            operation="coordination.goal",
            goal=body["text"],
            memoryKeys=body.get("memoryKeys", []),
            status="READY",
            mode="sandbox",
            result=None,
            plan=None,
            planRevision=0,
            goalRevision=1,
            dispatchEpoch=1,
            stepStates={},
            planContext=[],
            intents={},
            modelCalls=0,
            toolCalls=0,
            wakeSeq=0,
            handledWake=0,
            runEpoch=0,
            leaseOwner=None,
            leaseUntil=0,
            executionAuthorized=True,
            grantEpoch=ctx.member.get("accessEpoch", 1),
            quotaActive=True,
            occurrence=occurrence,
            createdAt=self.domain.now(),
            updatedAt=self.domain.now(),
            wait=None,
            error=None,
        )
        return (
            {"id": tid, "rev": 1, "status": "READY"},
            [
                put("Domain", task),
                put("Delivery", self.intent(task)),
                put(
                    "Domain",
                    revised(ctx.household, activeTasks=ctx.household["activeTasks"] + 1),
                    ctx.household,
                ),
                self.domain.event(ctx, tid, 1, wake=True),
            ],
            False,
        )

    def change(self, ctx, tid, body, version, action):
        task = self.get(ctx, tid)
        self.domain.require_version(task, version)
        values = dict(
            leaseOwner=None,
            leaseUntil=0,
            runEpoch=task["runEpoch"] + 1,
            dispatchEpoch=task["dispatchEpoch"] + 1,
            updatedAt=self.domain.now(),
            error=None,
        )
        writes = []
        if action == "amend":
            if task["status"] == "CANCELLED" or task.get("cancelRequested"):
                raise Problem(409, "GOAL_CANCELLED", "Cancelled goals cannot be amended.")
            if not task["quotaActive"]:
                if ctx.household["activeTasks"] >= self.domain.settings.max_tasks:
                    raise Problem(409, "TASK_LIMIT", "Household active task ceiling reached.")
                values["quotaActive"] = True
                writes.append(
                    put(
                        "Domain",
                        revised(ctx.household, activeTasks=ctx.household["activeTasks"] + 1),
                        ctx.household,
                    )
                )
            values.update(
                goal=body["text"],
                label=body["text"][:200],
                memoryKeys=body["memoryKeys"],
                goalRevision=task["goalRevision"] + 1,
                plan=None,
                stepStates={},
                result=None,
                status="PAUSED" if task["status"] == "PAUSED" else "READY",
            )
        elif action == "pause":
            if task["status"] in TERMINAL | {"PAUSED", "CANCELLING"}:
                raise Problem(409, "INVALID_TRANSITION", "Only active goals can be paused.")
            values["status"] = "PAUSED"
        elif action == "resume":
            if task["status"] != "PAUSED":
                raise Problem(409, "INVALID_TRANSITION", "Only paused goals can resume.")
            if task["grantEpoch"] != ctx.member.get("accessEpoch", 1):
                raise Problem(403, "ACCESS_REVOKED", "The original goal authorization expired.")
            # Undispatched reservations are invalidated by pause; resume obtains fresh terms.
            values.update(status="READY", plan=None, stepStates={})
        elif action == "cancel":
            if task["status"] in {"CANCELLED", "CANCELLING"}:
                raise Problem(409, "INVALID_TRANSITION", "Goal cancellation already requested.")
            values.update(status="CANCELLING", cancelRequested=True, plan=None, stepStates={})
        else:
            raise ValueError("Unknown goal command")
        new = revised(task, **values)
        old = self.store.get("Delivery", (f"GOALRUN#{tid}", "META"))
        writes += [
            put("Domain", new, task),
            put("Delivery", self.intent(new, old), old),
            self.domain.event(ctx, tid, new["rev"], wake=True),
        ]
        return {"id": tid, "rev": new["rev"], "status": new["status"]}, writes, False

    def decide(self, ctx, tid, body, version):
        task = self.get(ctx, tid)
        self.domain.require_version(task, version)
        state = task["stepStates"].get(body["stepId"])
        if (
            task["status"] != "WAITING_APPROVAL"
            or not state
            or state["status"] != "WAITING_APPROVAL"
        ):
            raise Problem(409, "DECISION_NOT_PENDING", "No current decision for this step.")
        quote, _ = self.actions.current_quote(ctx, state["quoteId"])
        approval = self.actions.get(ctx, "APPROVAL", body["approvalId"])
        if (
            approval["quoteId"] != quote["id"]
            or approval["consumed"]
            or approval["expiresAt"] <= self.domain.now()
        ):
            raise Problem(409, "APPROVAL_STALE", "Decision does not match the current quote.")
        states = copy.deepcopy(task["stepStates"])
        states[body["stepId"]].update(approvalId=body["approvalId"], status="QUOTED")
        new = revised(task, stepStates=states, status="READY", wakeSeq=task["wakeSeq"] + 1)
        old = self.store.get("Delivery", (f"GOALRUN#{tid}", "META"))
        return (
            {"id": tid, "rev": new["rev"]},
            [
                guard("Domain", approval),
                guard("Domain", quote),
                put("Domain", new, task),
                put("Delivery", self.intent(new, old), old),
                self.domain.event(ctx, tid, new["rev"], wake=True),
            ],
            False,
        )

    def wake(self, h, tid, *, event_id=None):
        inbox_key = (f"INBOX#goals#{event_id}", "META") if event_id else None
        for _ in range(6):
            if inbox_key and self.store.get("Delivery", inbox_key):
                return
            task = self.store.get("Domain", (hkey(h), f"TASK#{tid}"))
            if (
                not task
                or task.get("operation") != "coordination.goal"
                or task["status"] in TERMINAL
            ):
                return
            old = self.store.get("Delivery", (f"GOALRUN#{tid}", "META"))
            new = revised(task, wakeSeq=task["wakeSeq"] + 1)
            due = (
                task["leaseUntil"] if task["leaseUntil"] > self.domain.now() else self.domain.now()
            )
            writes = [put("Domain", new, task), put("Delivery", self.intent(new, old, due), old)]
            if inbox_key:
                writes.append(
                    put(
                        "Delivery",
                        row(
                            *inbox_key,
                            receivedAt=self.domain.now(),
                            expiresAt=self.domain.now() + 30 * 86400,
                        ),
                    )
                )
            try:
                self.store.transact(writes)
                return
            except Conflict:
                continue
        raise Conflict("Goal wake contention")

    def consume(self, event):
        if event["type"] == "koyori.task.changed.v1" and event.get("wake"):
            # Commands already persist readiness. Queue hints never reopen a decision or a failed planner.
            task = self.store.get(
                "Domain", (hkey(event["householdId"]), f"TASK#{event['aggregateId']}")
            )
            if task and task.get("operation") == "coordination.goal" and task["status"] == "READY":
                self.wake(event["householdId"], event["aggregateId"], event_id=event["eventId"])
        elif event["type"] == "koyori.action.changed.v1":
            action = self.store.get(
                "Domain", (hkey(event["householdId"]), f"ACTION#{event['aggregateId']}")
            )
            if action and action.get("goalId"):
                self.wake(event["householdId"], action["goalId"], event_id=event["eventId"])
        elif event["type"] in {
            "koyori.memory.changed.v1",
            "koyori.calendar.changed.v1",
            "koyori.connection.changed.v1",
        }:
            deps, _ = self.store.query(
                "Delivery",
                f"PLANDEP#{event['householdId']}#{event['type'].split('.')[1]}#{event['aggregateId']}",
                limit=self.domain.settings.max_tasks,
                index="GSI2",
            )
            for dep in deps:
                self.invalidate(event, (dep["PK"], dep["SK"]))

    def invalidate(self, event, dependency_key):
        for _ in range(6):
            dep = self.store.get("Delivery", dependency_key)
            if not dep or "GSI2PK" not in dep:
                return
            task = self.store.get("Domain", (hkey(event["householdId"]), f"TASK#{dep['taskId']}"))
            if (
                not task
                or task["status"] in TERMINAL | {"PAUSED", "CANCELLING"}
                or task["planRevision"] != dep["planRevision"]
                or not task["plan"]
                or event["aggregateVersion"] <= dep["sourceRevision"]
            ):
                return
            old = self.store.get("Delivery", (f"GOALRUN#{task['id']}", "META"))
            new = revised(
                task,
                plan=None,
                stepStates={},
                status="READY",
                dispatchEpoch=task["dispatchEpoch"] + 1,
                runEpoch=task["runEpoch"] + 1,
                leaseOwner=None,
                leaseUntil=0,
                updatedAt=self.domain.now(),
            )
            try:
                self.store.transact(
                    [
                        guard("Delivery", dep),
                        put("Domain", new, task),
                        put("Delivery", self.intent(new, old), old),
                    ]
                )
                return
            except Conflict:
                continue
        raise Conflict("Goal context invalidation contention")

    def acquire(self, h, tid):
        for _ in range(6):
            task = self.store.get("Domain", (hkey(h), f"TASK#{tid}"))
            old = self.store.get("Delivery", (f"GOALRUN#{tid}", "META"))
            if (
                not task
                or task.get("operation") != "coordination.goal"
                or not old
                or old["status"] != "PENDING"
                or old["dueAt"] > self.domain.now()
            ):
                return None
            if task["status"] in TERMINAL or task["leaseUntil"] > self.domain.now():
                return None
            new = revised(
                task,
                leaseOwner=uid(),
                leaseUntil=self.domain.now() + RUN_SECONDS,
                runEpoch=task["runEpoch"] + 1,
                handledWake=task["wakeSeq"],
                status=task["status"] if task["status"] in {"PAUSED", "CANCELLING"} else "RUNNING",
            )
            try:
                self.store.transact(
                    [
                        put("Domain", new, task),
                        put("Delivery", self.intent(new, old, new["leaseUntil"]), old),
                    ]
                )
                return new
            except Conflict:
                continue
        raise Conflict("Goal lease contention")

    def current(self, run):
        task = self.store.get("Domain", (run["PK"], run["SK"]))
        if (
            not task
            or task["runEpoch"] != run["runEpoch"]
            or task["leaseOwner"] != run["leaseOwner"]
            or task["leaseUntil"] <= self.domain.now()
        ):
            raise Problem(409, "RUN_SUPERSEDED", "A newer run or command owns this goal.")
        return task

    def _save(self, run, ctx, values, writes=(), *, due=None, release=True, notify=False):
        task = self.current(run)
        new = revised(task, **values, updatedAt=self.domain.now())
        changes = list(writes)
        if release:
            new.update(leaseOwner=None, leaseUntil=0)
            old = self.store.get("Delivery", (f"GOALRUN#{task['id']}", "META"))
            if task["wakeSeq"] > task["handledWake"] and new["status"] not in TERMINAL:
                due = self.domain.now()
            intent = self.intent(new, old, due) if due is not None else self.domain.done_intent(old)
            changes.append(put("Delivery", intent, old))
        if new["status"] in TERMINAL and task["quotaActive"]:
            new["quotaActive"] = False
            household = self.store.get("Domain", (task["PK"], "META"))
            changes.append(
                put(
                    "Domain",
                    revised(household, activeTasks=household["activeTasks"] - 1),
                    household,
                )
            )
            changes.extend(self.unwatch(task, task.get("planContext", [])))
        changes += [put("Domain", new, task), self.domain.event(ctx, task["id"], new["rev"])]
        if notify:
            from koyori.notifications import Notifications

            changes += Notifications(self.domain).queue(ctx, "goal", task["id"], new["status"])
        transaction = unique(ctx.guards() + changes)
        if len(transaction) > 100:
            raise Problem(422, "PLAN_TRANSACTION_LIMIT", "Narrow the context before proceeding.")
        self.store.transact(transaction)
        return new

    def context_payload(self, ctx, task):
        memory = Memory(self.domain)
        body = ContextQuery(limit=8, maxCharacters=8000).model_dump()
        page = memory.context(ctx, body)
        items, truncated = page["items"], page["truncated"]
        for key in task["memoryKeys"]:
            page = memory.context(ctx, {**body, "key": key})
            items += page["items"]
            truncated |= page["truncated"]
        items = list({item["id"]: item for item in items}.values())
        truncated |= len(items) > 14
        items = items[:14]
        accounts, after, scanned = [], None, 0
        # Historical tombstones and other owners must not masquerade as an absent account.
        while scanned < 500:
            connections, after = self.store.query(
                "Domain", hkey(ctx.h), prefix="CONNECTION#", limit=100, after=after
            )
            scanned += len(connections)
            accounts += [
                c
                for c in connections
                if c["owner"] == ctx.actor
                and active(c, self.domain.now())
                and c.get("memberEpoch", 1) == ctx.member.get("accessEpoch", 1)
            ]
            if not after or len(accounts) > 8:
                break
        connections_truncated = bool(after) or len(accounts) > 8
        truncated |= connections_truncated
        accounts = accounts[:8]
        calendar_data = []
        calendar_reads = 0
        for connection in accounts:
            if connection["provider"] == "google-calendar":
                if calendar_reads == 2:
                    truncated = True
                    break
                snapshot = self.calendar_snapshot(ctx, task, connection["id"])
                calendar_data.append({"connectionId": connection["id"], **snapshot})
                truncated |= bool(snapshot.get("nextCursor"))
                calendar_reads += 1
        # Only approved projections; connection envelopes, grants and provider keys stay outside prompts.
        payload = dict(
            goal=task["goal"],
            now=self.domain.now(),
            timeZone=ctx.profile.get("timeZone", ctx.household["timeZone"]),
            memories=[
                {k: m[k] for k in ("id", "rev", "kind", "text", "key", "steps", "source") if k in m}
                for m in items
            ],
            connections=[
                {k: c[k] for k in ("id", "rev", "provider", "mode", "capabilities")}
                for c in accounts
            ],
            calendarData=calendar_data,
            existingIntents=[
                {
                    "intentKey": k,
                    "capability": v["capability"],
                    "connectionId": v["connectionId"],
                    "terms": self.intent_terms(ctx, v),
                }
                for k, v in task["intents"].items()
            ],
            contextTruncated=truncated,
            connectionsTruncated=connections_truncated,
        )
        while len(json.dumps(payload, ensure_ascii=False).encode()) > 20000:
            if payload["calendarData"]:
                payload["calendarData"].pop()
            elif payload["memories"]:
                payload["memories"].pop()
            else:
                raise Problem(422, "PLANNING_CONTEXT_LIMIT", "Context exceeds the planning bound.")
            payload["contextTruncated"] = True
        return payload

    def intent_terms(self, ctx, intent):
        if not intent["actions"]:
            return None
        action = self.actions.get(ctx, "ACTION", intent["actions"][-1])
        return {
            "lines": action["conditions"]["lines"],
            "deliveryAt": action["conditions"]["deliveryAt"],
            "status": action["status"],
        }

    def unwatch(self, task, references):
        writes = []
        for reference in references:
            item = self.store.get(
                "Delivery",
                (
                    f"PLANDEP#{task['PK'][2:]}#{reference['kind']}#{reference['id']}",
                    f"TASK#{task['id']}",
                ),
            )
            if item and "GSI2PK" in item:
                new = revised(item)
                new.pop("GSI2PK", None)
                new.pop("GSI2SK", None)
                writes.append(put("Delivery", new, item))
        return writes

    def watch(self, task, references, revision):
        writes = []
        for reference in references:
            key = (
                f"PLANDEP#{task['PK'][2:]}#{reference['kind']}#{reference['id']}",
                f"TASK#{task['id']}",
            )
            previous = self.store.get("Delivery", key)
            writes.append(
                put(
                    "Delivery",
                    row(
                        *key,
                        rev=previous["rev"] + 1 if previous else 1,
                        taskId=task["id"],
                        planRevision=revision,
                        sourceRevision=reference["revision"],
                        GSI2PK=key[0],
                        GSI2SK=key[1],
                    ),
                    previous,
                )
            )
        return writes

    def calendar_snapshot(self, ctx, task, cid):
        if self.domain.settings.calendar_reader_arn:
            response = self.domain.settings.client("lambda").invoke(
                FunctionName=self.domain.settings.calendar_reader_arn,
                Payload=json.dumps(
                    {
                        "goalRead": True,
                        "householdId": ctx.h,
                        "taskId": task["id"],
                        "runEpoch": task["runEpoch"],
                        "connectionId": cid,
                    }
                ).encode(),
            )
            raw = response["Payload"].read(32769)
            if len(raw) > 32768 or response.get("FunctionError"):
                raise Problem(503, "CALENDAR_SPECIALIST_UNAVAILABLE", "Calendar reader failed.")
            data = json.loads(raw)
            if (
                data.get("evidence") != "calendar_snapshot"
                or data.get("connectionId") != cid
                or not isinstance(data.get("items"), list)
                or type(data.get("snapshotRevision")) is not int
                or data["snapshotRevision"] < 1
            ):
                raise Problem(
                    502, "INVALID_SPECIALIST_RESULT", "Calendar reader returned invalid evidence."
                )
            return data
        return calendar_snapshot(self.calendar, ctx, cid)

    def _plan(self, run, ctx):
        task = self.current(run)
        planning = self.planning or planner(self.domain.settings)
        payload = self.context_payload(ctx, task)
        quota = CallQuota(self.domain, ctx.h, task["id"], task["runEpoch"])
        error = None
        for _ in range(2):
            try:
                candidate = planning.generate(payload, quota, repair=error)
                accepted, checks = validate_plan(
                    self.domain,
                    ctx,
                    candidate,
                    allowed_connections={c["id"] for c in payload["connections"]},
                    allowed_memories={m["id"] for m in payload["memories"]},
                )
                # Every context item used by a model remains current at promotion, even if omitted from its references.
                for item in payload["memories"]:
                    current = Memory(self.domain).get(ctx, item["id"])
                    if current["rev"] != item["rev"]:
                        raise Problem(409, "PLAN_CONTEXT_CHANGED", "Planning context changed.")
                    checks.append(guard("Domain", current))
                if accepted["disposition"] == "ready":
                    planned_intents = {
                        s["arguments"]["intentKey"]
                        for s in accepted["steps"]
                        if s["kind"] == "write"
                    }
                    for key, intent in task["intents"].items():
                        if key not in planned_intents:
                            raise Problem(
                                409,
                                "ENGAGED_INTENT_OMITTED",
                                "Explicitly resolve the existing purchase before omitting it.",
                            )
                        for step in accepted["steps"]:
                            if (
                                step["kind"] == "write"
                                and step["arguments"]["intentKey"] == key
                                and (
                                    step["capability"] != intent["capability"]
                                    or step["arguments"]["connectionId"] != intent["connectionId"]
                                )
                            ):
                                raise Problem(
                                    409,
                                    "ENGAGED_INTENT_CHANGED",
                                    "An amendment cannot silently replace the purchase account or capability.",
                                )
                states = {s["stepId"]: {"status": "PENDING"} for s in accepted["steps"]}
                revision = task["planRevision"] + 1
                context_refs = [
                    {"kind": "memory", "id": m["id"], "revision": m["rev"]}
                    for m in payload["memories"]
                ]
                context_refs += [
                    {"kind": "connection", "id": c["id"], "revision": c["rev"]}
                    for c in payload["connections"]
                ]
                context_refs += [
                    {"kind": "calendar", "id": c["connectionId"], "revision": c["snapshotRevision"]}
                    for c in payload["calendarData"]
                ]
                references = {(ref["kind"], ref["id"]): ref for ref in context_refs}
                for reference in accepted["references"]:
                    key = reference["kind"], reference["id"]
                    previous = references.get(key)
                    if previous and previous["revision"] != reference["revision"]:
                        raise Problem(409, "PLAN_CONTEXT_CHANGED", "Declared plan source changed.")
                    references[key] = reference
                if len(references) > MAX_PLAN_SOURCES:
                    raise Problem(422, "PLAN_SOURCE_LIMIT", "Narrow the context before proceeding.")
                # Every accepted declared dependency survives promotion, including unsampled calendars.
                context_refs = list(references.values())
                checks += validate_goal_sources(
                    self.domain, ctx, {**task, "planContext": context_refs}
                )
                dependencies = []
                new_ids = {(reference["kind"], reference["id"]) for reference in context_refs}
                dependencies += self.unwatch(
                    task,
                    [
                        ref
                        for ref in task.get("planContext", [])
                        if (ref["kind"], ref["id"]) not in new_ids
                    ],
                )
                dependencies += self.watch(task, context_refs, revision)
                history = row(
                    task["PK"],
                    f"PLAN#{task['id']}#{revision:06d}",
                    plan=accepted,
                    planRevision=revision,
                    goalRevision=task["goalRevision"],
                    model=metadata(self.domain.settings, planning.mode),
                    tokenUsage=quota.usage,
                    createdAt=self.domain.now(),
                )
                status = "READY" if accepted["disposition"] == "ready" else "NEEDS_ATTENTION"
                return self._save(
                    run,
                    ctx,
                    dict(
                        plan=accepted,
                        planRevision=revision,
                        stepStates=states,
                        planContext=context_refs,
                        model=history["model"],
                        status=status,
                        error=None,
                        wait=None
                        if status == "READY"
                        else {"kind": "decision", "message": accepted["clarification"]},
                    ),
                    checks + dependencies + [put("Domain", history)],
                    due=self.domain.now() if status == "READY" else None,
                    notify=status != "READY",
                )
            except (ValidationError, ValueError) as exc:
                error = {"code": "INVALID_PLAN", "errorClass": type(exc).__name__}
        raise Problem(422, "INVALID_PLAN", "Model output failed validation after one repair.")

    def _pending(self, task):
        actions = [
            self.store.get("Domain", (task["PK"], f"ACTION#{aid}"))
            for intent in task["intents"].values()
            for aid in intent["actions"]
        ]
        return [a for a in actions if a and a["status"] in PENDING_ACTIONS]

    def _read(self, ctx, step, task=None):
        if step["capability"] == "memory.context":
            found = Memory(self.domain).context(ctx, step["arguments"])
            return SpecialistResult(
                capability="memory.context",
                evidence="canonical_memory",
                sources=[
                    {"kind": "memory", "id": m["id"], "revision": m["rev"]} for m in found["items"]
                ],
                sourceIds=[m["id"] for m in found["items"]],
                truncated=found["truncated"],
                observedAt=self.domain.now(),
                mode="real",
            ).model_dump()
        page = self.calendar_snapshot(ctx, task, step["arguments"]["connectionId"])
        return SpecialistResult(
            capability="calendar.read",
            evidence="calendar_snapshot",
            connectionId=step["arguments"]["connectionId"],
            sources=[
                {
                    "kind": "calendar",
                    "id": step["arguments"]["connectionId"],
                    "revision": page["snapshotRevision"],
                }
            ],
            eventCount=len(page["items"]),
            truncated=bool(page.get("nextCursor")),
            observedAt=self.domain.now(),
            mode=page["mode"],
        ).model_dump()

    def _write(self, run, ctx, step):
        task = self.current(run)
        validate_goal_sources(self.domain, ctx, task)
        states, intents = copy.deepcopy(task["stepStates"]), copy.deepcopy(task["intents"])
        state = states[step["stepId"]]
        if state["status"] == "WAITING_APPROVAL" and not state.get("approvalId"):
            return self._save(
                run,
                ctx,
                dict(
                    status="WAITING_APPROVAL",
                    wait={
                        "kind": "approval",
                        "stepId": step["stepId"],
                        "quoteId": state["quoteId"],
                    },
                ),
            )
        args = step["arguments"]
        key = args["intentKey"]
        intent = intents.get(key)
        if not intent:
            if len(intents) >= 12:
                raise Problem(409, "INTENT_LIMIT", "Goal commercial intention ceiling reached.")
            intent = dict(
                intentionId=digest({"goal": task["id"], "key": key}),
                connectionId=args["connectionId"],
                capability=step["capability"],
                actions=[],
            )
            intents[key] = intent
        if len(intent["actions"]) >= 16:
            raise Problem(409, "ACTION_LIMIT", "Goal amendment ceiling reached.")
        latest = (
            self.store.get("Domain", (task["PK"], f"ACTION#{intent['actions'][-1]}"))
            if intent["actions"]
            else None
        )
        business = self.store.get(
            "Domain", (task["PK"], f"BUSINESS#{ctx.actor}#{intent['intentionId']}")
        )
        if latest and latest["status"] in PENDING_ACTIONS:
            states[step["stepId"]] = dict(status="WAITING_PROVIDER", actionId=latest["id"])
            return self._save(
                run,
                ctx,
                dict(
                    stepStates=states,
                    status="WAITING_PROVIDER",
                    wait={"kind": "provider", "actionId": latest["id"]},
                ),
                due=self.domain.now() + 30,
            )
        if state.get("actionId"):
            action = self.actions.get(ctx, "ACTION", state["actionId"])
            if action["status"] == "CONFIRMED" and action["receipt"]:
                state.update(status="DONE", evidence="provider_receipt", receipt=action["receipt"])
                return self._save(
                    run,
                    ctx,
                    dict(stepStates=states, status="READY", wait=None),
                    [guard("Domain", action)],
                    due=self.domain.now(),
                )
            raise Problem(
                409, "ACTION_NOT_CONFIRMED", "Provider did not confirm the requested operation."
            )
        target = None
        if business:
            unexecuted = (
                business["status"] in {"BLOCKED", "REJECTED"}
                and business["providerVersion"] == 0
                and not business.get("actionId")
            )
            if not unexecuted and (
                business["status"] != "CONFIRMED" or not business.get("actionId")
            ):
                raise Problem(
                    409,
                    "INTENTION_UNRESOLVED",
                    "Resolve the previous operation before retrying this intent.",
                )
            target = (
                self.actions.get(ctx, "ACTION", business["actionId"]) if not unexecuted else None
            )
            if target and (
                target["conditions"]["lines"] == args["lines"]
                and target["conditions"]["deliveryAt"] == args["deliveryAt"]
            ):
                state.update(
                    status="DONE",
                    evidence="provider_receipt",
                    actionId=target["id"],
                    receipt=target["receipt"],
                )
                return self._save(
                    run,
                    ctx,
                    dict(stepStates=states, status="READY", wait=None),
                    [guard("Domain", target), guard("Domain", business)],
                    due=self.domain.now(),
                )
        if not state.get("quoteId"):
            body = QuoteCreate(
                connectionId=args["connectionId"],
                capability=step["capability"],
                intentionId=intent["intentionId"],
                operation="modify" if target else "create",
                targetActionId=target["id"] if target else None,
                lines=args["lines"],
                deliveryAt=args["deliveryAt"],
            ).model_dump()
            quote, writes, _ = self.actions.quote(ctx, body, reuse_unexecuted=True)
            for change in writes:
                if change.item and change.key[1] == f"QUOTE#{quote['id']}":
                    change.item.update(
                        goalId=task["id"], goalEpoch=task["dispatchEpoch"], goalStep=step["stepId"]
                    )
            budget = self.actions.budget(ctx)
            approval = not budget or budget["approvalRequired"]
            state.update(status="WAITING_APPROVAL" if approval else "QUOTED", quoteId=quote["id"])
            status = "WAITING_APPROVAL" if approval else "READY"
            return self._save(
                run,
                ctx,
                dict(
                    stepStates=states,
                    intents=intents,
                    status=status,
                    wait={"kind": "approval", "stepId": step["stepId"], "quoteId": quote["id"]}
                    if approval
                    else None,
                ),
                writes,
                due=None if approval else self.domain.now(),
                notify=approval,
            )
        action, writes, _ = self.actions.reserve(
            ctx, {"quoteId": state["quoteId"], "approvalId": state.get("approvalId")}, goal_run=task
        )
        intent["actions"].append(action["id"])
        state.update(status="WAITING_PROVIDER", actionId=action["id"])
        return self._save(
            run,
            ctx,
            dict(
                stepStates=states,
                intents=intents,
                status="WAITING_PROVIDER",
                wait={"kind": "provider", "actionId": action["id"]},
            ),
            writes,
            due=self.domain.now() + 30,
        )

    def _cancel(self, run, ctx):
        task = self.current(run)
        if self._pending(task):
            return self._save(
                run,
                ctx,
                dict(status="CANCELLING", wait={"kind": "provider"}),
                due=self.domain.now() + 30,
            )
        for key, intent in task["intents"].items():
            business = self.store.get(
                "Domain", (task["PK"], f"BUSINESS#{ctx.actor}#{intent['intentionId']}")
            )
            if not business or business["status"] in {"CANCELLED", "BLOCKED", "REJECTED"}:
                continue
            target = self.actions.get(ctx, "ACTION", business["actionId"])
            if target["status"] != "CONFIRMED":
                raise Problem(
                    409, "CANCELLATION_UNRESOLVED", "Provider cancellation requires attention."
                )
            args = target["conditions"]
            body = QuoteCreate(
                connectionId=args["connectionId"],
                capability=args["capability"],
                intentionId=args["intentionId"],
                operation="cancel",
                targetActionId=target["id"],
                deliveryAt=args["deliveryAt"],
            ).model_dump()
            states = copy.deepcopy(task["stepStates"])
            state = states.setdefault(key, {})
            if not state.get("quoteId"):
                quote, writes, _ = self.actions.quote(ctx, body)
                for change in writes:
                    if change.item and change.key[1] == f"QUOTE#{quote['id']}":
                        change.item.update(
                            goalId=task["id"],
                            goalEpoch=task["dispatchEpoch"],
                            goalStep=key,
                            goalCancellation=True,
                        )
                state.update(quoteId=quote["id"], status="QUOTED")
                return self._save(
                    run,
                    ctx,
                    dict(status="CANCELLING", stepStates=states),
                    writes,
                    due=self.domain.now(),
                )
            action, writes, _ = self.actions.reserve(
                ctx, {"quoteId": state["quoteId"]}, goal_run=task
            )
            intents = copy.deepcopy(task["intents"])
            intents[key]["actions"].append(action["id"])
            states.pop(key, None)
            return self._save(
                run,
                ctx,
                dict(status="CANCELLING", intents=intents, stepStates=states),
                writes,
                due=self.domain.now() + 30,
            )
        return self._save(
            run, ctx, dict(status="CANCELLED", wait=None, result={"cancelled": True}), notify=True
        )

    def run(self, h, tid, *, run=None):
        run = run or self.acquire(h, tid)
        if not run:
            return
        try:
            ctx = self.domain.context(run["owner"], h)
            if ctx.member.get("accessEpoch", 1) != run["grantEpoch"]:
                raise Problem(403, "ACCESS_REVOKED", "Goal authority changed.")
            if run["status"] == "PAUSED":
                return self._save(
                    run,
                    ctx,
                    dict(status="PAUSED", wait={"kind": "pause"}),
                    due=self.domain.now() + 120,
                )
            if run.get("cancelRequested"):
                return self._cancel(run, ctx)
            if run.get("occurrence"):
                rule = self.store.get(
                    "Domain", (run["PK"], f"ROUTINE#{run['occurrence']['ruleId']}")
                )
                if (
                    not rule
                    or rule["paused"]
                    or rule["ruleVersion"] != run["occurrence"]["ruleVersion"]
                ):
                    return self._save(
                        run,
                        ctx,
                        dict(status="PAUSED", wait={"kind": "routine_changed"}),
                        due=self.domain.now() + 120,
                    )
            if not run["plan"]:
                if self._pending(run):
                    return self._save(
                        run,
                        ctx,
                        dict(status="WAITING_PROVIDER", wait={"kind": "provider"}),
                        due=self.domain.now() + 30,
                    )
                return self._plan(run, ctx)
            states = run["stepStates"]
            ready = [
                s
                for s in run["plan"]["steps"]
                if states[s["stepId"]]["status"] != "DONE"
                and all(states[d]["status"] == "DONE" for d in s["dependsOn"])
            ]
            future = [s["dueAt"] for s in ready if s["dueAt"] and s["dueAt"] > self.domain.now()]
            ready = [s for s in ready if not s["dueAt"] or s["dueAt"] <= self.domain.now()]
            if not ready:
                if future:
                    from koyori.scheduling import Wakes

                    due = min(future)
                    return self._save(
                        run,
                        ctx,
                        dict(status="WAITING_TIME", wait={"kind": "time", "dueAt": due}),
                        Wakes(self.domain).goal_wake(run, due),
                        due=due,
                    )
                if all(state["status"] == "DONE" for state in states.values()):
                    return self._save(
                        run,
                        ctx,
                        dict(status="SUCCEEDED", wait=None, result={"stepsConfirmed": len(states)}),
                        notify=True,
                    )
                raise Problem(409, "DEPENDENCY_BLOCKED", "A dependency needs a decision.")
            reads = [s for s in ready if s["kind"] == "read"][
                : min(run["plan"]["maxParallelReads"], run["plan"]["maxToolCalls"])
            ]
            if reads:
                with ThreadPoolExecutor(max_workers=run["plan"]["maxParallelReads"]) as pool:
                    futures = [(step, pool.submit(self._read, ctx, step, run)) for step in reads]

                    outcomes = [(step, future.result()) for step, future in futures]
                current = self.current(run)
                current_states = copy.deepcopy(current["stepStates"])
                references = {
                    (ref["kind"], ref["id"]): ref for ref in current.get("planContext", [])
                }
                added = {}
                for step, evidence in outcomes:
                    current_states[step["stepId"]] = dict(status="DONE", **evidence)
                    for reference in evidence["sources"]:
                        key = reference["kind"], reference["id"]
                        previous = references.get(key)
                        if previous and previous["revision"] != reference["revision"]:
                            raise Problem(409, "PLAN_CONTEXT_CHANGED", "Read source changed.")
                        if not previous:
                            references[key] = added[key] = reference
                if len(references) > MAX_PLAN_SOURCES:
                    raise Problem(422, "PLAN_SOURCE_LIMIT", "Narrow the context before proceeding.")
                context_refs = list(references.values())
                checks = validate_goal_sources(
                    self.domain, ctx, {**current, "planContext": context_refs}
                )
                # A read checkpoint and its newly discovered dependencies must commit together.
                checks += self.watch(current, added.values(), current["planRevision"])
                return self._save(
                    run,
                    ctx,
                    dict(
                        status="READY",
                        stepStates=current_states,
                        planContext=context_refs,
                        toolCalls=run["toolCalls"] + len(reads),
                    ),
                    checks,
                    due=self.domain.now(),
                )
            return self._write(run, ctx, ready[0])
        except Conflict:
            # A newer canonical state wins. Durable GOALRUN repairs the expired lease.
            return
        except Problem as exc:
            if exc.code == "RUN_SUPERSEDED":
                return
            self._error(run, exc.code)
        except Exception:
            self._error(run, "PLANNER_OR_CONNECTOR_UNAVAILABLE")

    def _error(self, run, code):
        try:
            ctx = self.domain.context(run["owner"], run["PK"][2:])
            if code == "ACCESS_REVOKED" or ctx.member.get("accessEpoch", 1) != run["grantEpoch"]:
                raise Problem(403, "ACCESS_REVOKED", "Original goal authority expired.")
            self._save(
                run,
                ctx,
                dict(status="NEEDS_ATTENTION", error=code, wait={"kind": "decision", "code": code}),
                notify=True,
            )
        except Problem as exc:
            if exc.code == "RUN_SUPERSEDED":
                return
            if exc.status != 403:
                raise
            # Revoked identity cannot authorize new work; pending provider reconciliation is independent.
            task = self.current(run)
            household = self.store.get("Domain", (task["PK"], "META"))
            old = self.store.get("Delivery", (f"GOALRUN#{task['id']}", "META"))
            new = revised(
                task,
                status="FAILED",
                error="ACCESS_REVOKED",
                leaseOwner=None,
                leaseUntil=0,
                quotaActive=False,
                dispatchEpoch=task["dispatchEpoch"] + 1,
            )
            writes = [put("Domain", new, task), put("Delivery", self.domain.done_intent(old), old)]
            writes += self.unwatch(task, task.get("planContext", []))
            if task["quotaActive"]:
                writes.append(
                    put(
                        "Domain",
                        revised(household, activeTasks=household["activeTasks"] - 1),
                        household,
                    )
                )
            self.store.transact(writes)

    def sweep(self):
        items = self.pending("GOALRUN")
        for candidate in items:
            current = self.store.get("Delivery", (candidate["PK"], candidate["SK"]))
            if current and current["status"] == "PENDING" and current["dueAt"] <= self.domain.now():
                self.run(current["h"], current["taskId"])
        return len(items)
