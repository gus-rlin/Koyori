"""Canonical wake registry and versioned civil-time occurrences; Scheduler is repairable delivery."""

import json
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from botocore.exceptions import ClientError

from koyori.domain import active, hkey, row, uid
from koyori.errors import Conflict, Problem, missing
from koyori.security import digest
from koyori.stage2 import Service
from koyori.store import guard, put, revised


def civil_timestamp(day, clock, zone, *, ambiguous="first", nonexistent="skip"):
    naive = datetime.combine(day, time.fromisoformat(clock))
    timezone = ZoneInfo(zone)
    candidates = sorted(
        {
            int(naive.replace(tzinfo=timezone, fold=fold).timestamp())
            for fold in (0, 1)
            if datetime.fromtimestamp(
                naive.replace(tzinfo=timezone, fold=fold).timestamp(), timezone
            ).replace(tzinfo=None)
            == naive
        }
    )
    if not candidates:
        if nonexistent == "reject":
            raise Problem(
                422, "NONEXISTENT_LOCAL_TIME", "Routine time does not exist on this local date."
            )
        return None
    return candidates[-1] if ambiguous == "second" else candidates[0]


def next_occurrence(rule, now, *, after_local=None):
    local_day = datetime.fromtimestamp(now, ZoneInfo(rule["timeZone"])).date()
    start = max(date.fromisoformat(rule["startsOn"]), local_day)
    end = date.fromisoformat(rule["endsOn"])
    while start <= end:
        local = f"{start.isoformat()}T{rule['localTime']}"
        if start.weekday() in rule["weekdays"] and (not after_local or local > after_local):
            due = civil_timestamp(
                start,
                rule["localTime"],
                rule["timeZone"],
                ambiguous=rule["ambiguousTime"],
                nonexistent=rule["nonexistentTime"],
            )
            if due is not None and due >= now:
                return due, local
        start += timedelta(days=1)
    return None


class Scheduler:
    def __init__(self, settings, client=None):
        self.settings = settings
        self.client = client or settings.client("scheduler")

    def ensure(self, wake):
        settings = self.settings
        desired = json.dumps({"wakeId": wake["id"]}, sort_keys=True, separators=(",", ":"))
        at = datetime.fromtimestamp(wake["fireAt"], UTC).strftime("%Y-%m-%dT%H:%M:%S")
        args = dict(
            Name=f"koyori-{wake['id']}",
            GroupName=settings.scheduler_group,
            ScheduleExpression=f"at({at})",
            ScheduleExpressionTimezone="UTC",
            FlexibleTimeWindow={"Mode": "OFF"},
            ActionAfterCompletion="DELETE",
            Target={
                "Arn": settings.scheduler_target_arn,
                "RoleArn": settings.scheduler_role_arn,
                "Input": desired,
                "RetryPolicy": {"MaximumEventAgeInSeconds": 86400, "MaximumRetryAttempts": 10},
            },
            ClientToken=digest({"wake": wake["id"], "due": wake["fireAt"]}),
        )
        try:
            self.client.create_schedule(**args)
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ConflictException":
                raise
            existing = self.client.get_schedule(Name=args["Name"], GroupName=args["GroupName"])
            if (
                existing["ScheduleExpression"] != args["ScheduleExpression"]
                or existing["Target"]["Input"] != desired
                or existing["Target"]["Arn"] != settings.scheduler_target_arn
            ):
                raise Problem(
                    409, "SCHEDULE_CONFLICT", "Scheduler name has different immutable input."
                ) from exc

    def remove(self, wake):
        try:
            self.client.delete_schedule(
                Name=f"koyori-{wake['id']}",
                GroupName=self.settings.scheduler_group,
                ClientToken=digest({"delete": wake["id"]}),
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ResourceNotFoundException":
                raise


class Wakes(Service):
    def __init__(self, domain, scheduler=None):
        super().__init__(domain)
        self.scheduler = scheduler
        if self.scheduler is None and domain.settings.scheduler_group:
            self.scheduler = Scheduler(domain.settings)

    def rule_check(self, rule):
        due = self.domain.now() + 120
        return row(
            f"RULECHECK#{rule['id']}",
            h=rule["PK"][2:],
            ruleId=rule["id"],
            status="PENDING",
            dueAt=due,
            GSI1PK=f"RULECHECK#{int(rule['id'][:8], 16) % self.domain.settings.shards}",
            GSI1SK=f"{due:020d}#{rule['id']}",
        )

    def record(self, identifier, due, **values):
        return row(
            f"WAKE#{identifier}",
            id=identifier,
            fireAt=due,
            dueAt=self.domain.now(),
            status="PENDING",
            desired="CREATE",
            schedulerState="PENDING",
            GSI1PK=f"WAKERUN#{int(identifier[:8], 16) % self.domain.settings.shards}",
            GSI1SK=f"{self.domain.now():020d}#{identifier}",
            **values,
        )

    def goal_wake(self, task, due):
        identifier = digest(
            {
                "goal": task["id"],
                "epoch": task["dispatchEpoch"],
                "plan": task["planRevision"],
                "due": due,
            }
        )[:32]
        old = self.store.get("Delivery", (f"WAKE#{identifier}", "META"))
        if old:
            return [guard("Delivery", old)]
        return [
            put(
                "Delivery",
                self.record(
                    identifier,
                    due,
                    kind="goal",
                    h=task["PK"][2:],
                    owner=task["owner"],
                    taskId=task["id"],
                    goalEpoch=task["dispatchEpoch"],
                    planRevision=task["planRevision"],
                ),
            )
        ]

    def rule_wake(self, rule, due, local):
        identifier = digest({"rule": rule["id"], "version": rule["ruleVersion"], "local": local})[
            :32
        ]
        return self.record(
            identifier,
            due,
            kind="routine",
            h=rule["PK"][2:],
            owner=rule["owner"],
            ruleId=rule["id"],
            ruleVersion=rule["ruleVersion"],
            localOccurrence=local,
        )

    def get_rule(self, ctx, rid):
        self.domain.personal(ctx)
        rule = self.store.get("Domain", (hkey(ctx.h), f"ROUTINE#{rid}"))
        if not rule or rule["owner"] != ctx.actor:
            raise missing()
        return rule

    def create_rule(self, ctx, body):
        if ctx.household.get("activeRoutines", 0) >= 32:
            raise Problem(409, "ROUTINE_LIMIT", "Household routine ceiling reached.")
        rule = row(
            hkey(ctx.h),
            f"ROUTINE#{uid()}",
            owner=ctx.actor,
            active=True,
            paused=False,
            ruleVersion=1,
            memberEpoch=ctx.member.get("accessEpoch", 1),
            createdAt=self.domain.now(),
            **body,
        )
        rule["id"] = rule["SK"][8:]
        next_time = next_occurrence(rule, self.domain.now())
        if not next_time:
            raise Problem(
                422, "ROUTINE_EXPIRED", "No future occurrence within the routine horizon."
            )
        wake = self.rule_wake(rule, *next_time)
        rule["wakeId"] = wake["id"]
        # Household revision fences concurrent admissions to the bounded rule set.
        return (
            {"id": rule["id"], "rev": 1},
            [
                put("Domain", rule),
                put("Delivery", wake),
                put("Delivery", self.rule_check(rule)),
                put(
                    "Domain",
                    revised(
                        ctx.household, activeRoutines=ctx.household.get("activeRoutines", 0) + 1
                    ),
                    ctx.household,
                ),
                self.domain.event(ctx, rule["id"], rule["rev"], kind="routine"),
            ],
            False,
        )

    def change_rule(self, ctx, rid, body, version, action):
        old = self.get_rule(ctx, rid)
        self.domain.require_version(old, version)
        if not old["active"]:
            raise Problem(409, "ROUTINE_CANCELLED", "Routine has been cancelled.")
        values = dict(ruleVersion=old["ruleVersion"] + 1)
        if action == "amend":
            values.update(body)
        elif action == "pause":
            if old["paused"]:
                raise Problem(409, "INVALID_TRANSITION", "Routine is already paused.")
            values["paused"] = True
        elif action == "resume":
            if not old["paused"]:
                raise Problem(409, "INVALID_TRANSITION", "Routine is not paused.")
            if old["memberEpoch"] != ctx.member.get("accessEpoch", 1):
                raise Problem(403, "ACCESS_REVOKED", "The original routine authorization expired.")
            values["paused"] = False
        elif action == "cancel":
            values["active"] = False
        else:
            raise ValueError("Unknown routine command")
        new = revised(old, **values)
        writes = []
        wake = (
            self.store.get("Delivery", (f"WAKE#{old['wakeId']}", "META"))
            if old.get("wakeId")
            else None
        )
        if wake and wake["status"] == "PENDING":
            writes.append(
                put(
                    "Delivery",
                    revised(
                        wake,
                        desired="DELETE",
                        dueAt=self.domain.now(),
                        GSI1SK=f"{self.domain.now():020d}#{wake['id']}",
                    ),
                    wake,
                )
            )
        if new["active"] and not new["paused"]:
            next_time = next_occurrence(new, self.domain.now())
            if not next_time:
                raise Problem(422, "ROUTINE_EXPIRED", "No future occurrence remains.")
            pending = self.rule_wake(new, *next_time)
            writes.append(put("Delivery", pending))
            new["wakeId"] = pending["id"]
        else:
            new["wakeId"] = None
        if not new["active"]:
            writes.append(
                put(
                    "Domain",
                    revised(
                        ctx.household, activeRoutines=ctx.household.get("activeRoutines", 0) - 1
                    ),
                    ctx.household,
                )
            )
        writes.append(put("Domain", new, old))
        writes.append(self.domain.event(ctx, rid, new["rev"], kind="routine"))
        return {"id": rid, "rev": new["rev"]}, writes, False

    def _done(self, wake, *, outcome):
        new = self.domain.done_intent(wake)
        new.update(outcome=outcome, desired="DELETE", schedulerState="DELETE_PENDING")
        new["dueAt"] = self.domain.now()
        # Deletion is independently repairable even after the occurrence transaction.
        new["GSI1PK"] = f"WAKEDELETE#{int(wake['id'][:8], 16) % self.domain.settings.shards}"
        new["GSI1SK"] = f"{self.domain.now():020d}#{wake['id']}"
        return new

    def deliver(self, identifier):
        for _ in range(6):
            wake = self.store.get("Delivery", (f"WAKE#{identifier}", "META"))
            if not wake or wake["status"] != "PENDING" or wake["fireAt"] > self.domain.now():
                return
            if wake["desired"] == "DELETE":
                self.store.transact([put("Delivery", self._done(wake, outcome="CANCELLED"), wake)])
                return
            writes = []
            if wake["kind"] == "goal":
                from koyori.goals import Goals

                task = self.store.get("Domain", (hkey(wake["h"]), f"TASK#{wake['taskId']}"))
                valid = bool(
                    task
                    and task["dispatchEpoch"] == wake["goalEpoch"]
                    and task["planRevision"] == wake["planRevision"]
                    and task["status"] not in {"SUCCEEDED", "FAILED", "CANCELLED", "PAUSED"}
                )
                if valid:
                    new = revised(task, wakeSeq=task["wakeSeq"] + 1)
                    intent = self.store.get("Delivery", (f"GOALRUN#{task['id']}", "META"))
                    due = (
                        task["leaseUntil"]
                        if task["leaseUntil"] > self.domain.now()
                        else self.domain.now()
                    )
                    writes += [
                        put("Domain", new, task),
                        put("Delivery", Goals(self.domain).intent(new, intent, due), intent),
                    ]
                elif task:
                    writes.append(guard("Domain", task))
            else:
                authority_revoked = False
                rule = self.store.get("Domain", (hkey(wake["h"]), f"ROUTINE#{wake['ruleId']}"))
                valid = bool(
                    rule
                    and rule["active"]
                    and not rule["paused"]
                    and rule["ruleVersion"] == wake["ruleVersion"]
                    and rule.get("wakeId") == wake["id"]
                )
                if valid:
                    try:
                        ctx = self.domain.context(rule["owner"], wake["h"])
                        valid = ctx.member.get("accessEpoch", 1) == rule["memberEpoch"]
                        authority_revoked = not valid
                    except Problem as exc:
                        if exc.status not in {403, 404}:
                            raise
                        valid = False
                        authority_revoked = True
                if valid:
                    from koyori.goals import Goals

                    occurrence_id = digest(
                        {
                            "rule": rule["id"],
                            "version": rule["ruleVersion"],
                            "local": wake["localOccurrence"],
                        }
                    )[:32]
                    occurrence_key = (rule["PK"], f"OCCURRENCE#{occurrence_id}")
                    occurrence = self.store.get("Domain", occurrence_key)
                    if not occurrence:
                        body = {"text": rule["text"], "memoryKeys": rule["memoryKeys"]}
                        _, goal_writes, _ = Goals(self.domain).create(
                            ctx,
                            body,
                            task_id=occurrence_id,
                            occurrence={
                                "ruleId": rule["id"],
                                "ruleVersion": rule["ruleVersion"],
                                "local": wake["localOccurrence"],
                            },
                        )
                        writes += (
                            ctx.guards()
                            + goal_writes
                            + [put("Domain", row(*occurrence_key, taskId=occurrence_id))]
                        )
                    next_time = next_occurrence(
                        rule, self.domain.now(), after_local=wake["localOccurrence"]
                    )
                    new_rule = revised(rule, lastOccurrence=wake["localOccurrence"], wakeId=None)
                    if next_time:
                        pending = self.rule_wake(rule, *next_time)
                        new_rule["wakeId"] = pending["id"]
                        writes.append(put("Delivery", pending))
                    else:
                        new_rule["active"] = False
                        household_write = next(
                            (
                                w
                                for w in writes
                                if w.table == "Domain"
                                and w.key == (hkey(ctx.h), "META")
                                and w.item is not None
                            ),
                            None,
                        )
                        if household_write:
                            household_write.item["activeRoutines"] = (
                                ctx.household.get("activeRoutines", 0) - 1
                            )
                        else:
                            writes.append(
                                put(
                                    "Domain",
                                    revised(
                                        ctx.household,
                                        activeRoutines=ctx.household.get("activeRoutines", 0) - 1,
                                    ),
                                    ctx.household,
                                )
                            )
                    writes.append(put("Domain", new_rule, rule))
                elif rule:
                    if authority_revoked:
                        household = self.store.get("Domain", (rule["PK"], "META"))
                        writes += [
                            put(
                                "Domain",
                                revised(
                                    rule,
                                    active=False,
                                    paused=True,
                                    wakeId=None,
                                    ruleVersion=rule["ruleVersion"] + 1,
                                ),
                                rule,
                            ),
                            put(
                                "Domain",
                                revised(
                                    household, activeRoutines=household.get("activeRoutines", 0) - 1
                                ),
                                household,
                            ),
                        ]
                    else:
                        writes.append(guard("Domain", rule))
            writes.append(
                put("Delivery", self._done(wake, outcome="FIRED" if valid else "STALE"), wake)
            )
            try:
                self.store.transact(writes)
                return
            except Conflict:
                continue
        raise Conflict("Wake occurrence contention")

    def check_rule(self, candidate):
        check = self.store.get("Delivery", (candidate["PK"], candidate["SK"]))
        if not check or check["status"] != "PENDING" or check["dueAt"] > self.domain.now():
            return
        rule = self.store.get("Domain", (hkey(check["h"]), f"ROUTINE#{check['ruleId']}"))
        if not rule or not rule["active"]:
            self.store.transact([put("Delivery", self.domain.done_intent(check), check)])
            return
        member = self.store.get("Domain", (rule["PK"], f"MEMBER#{rule['owner']}"))
        profile = self.store.get("Domain", (f"P#{rule['owner']}", "PROFILE"))
        household = self.store.get("Domain", (rule["PK"], "META"))
        valid = bool(
            household
            and active(member, self.domain.now())
            and active(profile, self.domain.now())
            and profile["kind"] == "personal"
            and member.get("accessEpoch", 1) == rule["memberEpoch"]
        )
        expired = datetime.fromtimestamp(
            self.domain.now(), ZoneInfo(rule["timeZone"])
        ).date() > date.fromisoformat(rule["endsOn"])
        guards = [guard("Domain", item) for item in (rule, member, profile, household) if item]
        wake = (
            self.store.get("Delivery", (f"WAKE#{rule['wakeId']}", "META"))
            if rule.get("wakeId")
            else None
        )
        if (
            valid
            and expired
            and not rule["paused"]
            and wake
            and wake["status"] == "PENDING"
            and wake["desired"] == "CREATE"
            and wake["fireAt"] <= self.domain.now()
            and wake["ruleVersion"] == rule["ruleVersion"]
        ):
            # A restart past the horizon still owes the already persisted final occurrence.
            # deliver rechecks authority/rule and releases the quota atomically with that occurrence.
            self.deliver(wake["id"])
            return
        if valid and not expired:
            due = self.domain.now() + 120
            self.store.transact(
                guards
                + [
                    put(
                        "Delivery",
                        revised(check, dueAt=due, GSI1SK=f"{due:020d}#{rule['id']}"),
                        check,
                    )
                ]
            )
            return
        # Paused rules have no occurrence wake; this independent intent releases their quota.
        writes = [
            put("Delivery", self.domain.done_intent(check), check),
            put(
                "Domain",
                revised(
                    rule,
                    active=False,
                    paused=True,
                    wakeId=None,
                    ruleVersion=rule["ruleVersion"] + 1,
                ),
                rule,
            ),
        ]
        if household:
            writes.append(
                put(
                    "Domain",
                    revised(household, activeRoutines=household.get("activeRoutines", 0) - 1),
                    household,
                )
            )
        if wake and wake["status"] == "PENDING":
            writes.append(
                put(
                    "Delivery",
                    self._done(wake, outcome="EXPIRED" if expired else "ACCESS_REVOKED"),
                    wake,
                )
            )
        self.store.transact(guards + writes)

    def sweep(self):
        attempts = 0
        for candidate in self.pending("RULECHECK"):
            attempts += 1
            try:
                self.check_rule(candidate)
            except Conflict:
                continue
            except Exception:
                self.defer(candidate, self.domain.now() + 120)
        for category in ("WAKEDELETE", "WAKERUN"):
            for candidate in self.pending(category):
                wake = self.store.get("Delivery", (candidate["PK"], candidate["SK"]))
                if not wake or wake["rev"] != candidate["rev"]:
                    continue
                attempts += 1
                try:
                    if wake["desired"] == "DELETE":
                        if self.scheduler:
                            self.scheduler.remove(wake)
                        new = self.domain.done_intent(wake)
                        new["schedulerState"] = "DELETED"
                        self.store.transact([put("Delivery", new, wake)])
                    elif wake["fireAt"] <= self.domain.now():
                        self.deliver(wake["id"])
                    else:
                        if self.scheduler:
                            self.scheduler.ensure(wake)
                        self.store.transact(
                            [
                                put(
                                    "Delivery",
                                    revised(
                                        wake,
                                        schedulerState="SCHEDULED" if self.scheduler else "LOCAL",
                                        dueAt=wake["fireAt"],
                                        GSI1SK=f"{wake['fireAt']:020d}#{wake['id']}",
                                    ),
                                    wake,
                                )
                            ]
                        )
                except Conflict:
                    continue
                except Exception:
                    # A broken schedule cannot monopolize all due work.
                    self.defer(
                        wake, self.domain.now() + min(300, 30 * 2 ** min(wake.get("retries", 0), 4))
                    )
        return attempts
