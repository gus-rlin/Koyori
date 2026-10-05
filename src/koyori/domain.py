"""Household authority and durable control operations, shared by all transports.

Commands only operate on a synthetic checkpoint. Preferences, model plans and
client identity metadata never participate in permission decisions.
"""

import hashlib
import secrets
import time
import uuid
from dataclasses import dataclass

from koyori.config import Settings
from koyori.errors import Conflict, Problem, denied, missing
from koyori.security import Cursors, digest, idempotency_key, request_hash
from koyori.store import Change, Store, guard, put, revised

TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED"}


def uid() -> str:
    return uuid.uuid4().hex


def row(pk: str, sk: str = "META", **values) -> dict:
    return {"PK": pk, "SK": sk, "rev": 1, **values}


def hkey(h: str) -> str:
    return f"H#{h}"


def active(item: dict | None, now: int) -> bool:
    return bool(
        item
        and item.get("active", True)
        and (item.get("expiresAt") is None or item["expiresAt"] > now)
    )


def projection(item: dict) -> dict:
    return {
        key: value
        for key, value in item.items()
        if key
        not in {
            "PK",
            "SK",
            "GSI1PK",
            "GSI1SK",
            "GSI2PK",
            "GSI2SK",
            "leaseOwner",
            "leaseUntil",
            "grantOwner",
            "nonce",
            "memberIds",
        }
    }


@dataclass
class Context:
    actor: str
    household: dict
    member: dict
    profile: dict

    @property
    def h(self) -> str:
        return self.household["id"]

    def guards(self) -> list[Change]:
        return [guard("Domain", value) for value in (self.household, self.member, self.profile)]


class Domain:
    def __init__(self, store: Store, settings: Settings, cursors: Cursors, clock=time.time):
        self.store, self.settings, self.cursors, self.clock = store, settings, cursors, clock

    def now(self) -> int:
        return int(self.clock())

    def run_intent(self, task: dict, previous: dict | None, due: int | None = None) -> dict:
        """Persist readiness with the task; queue delivery is only an optimization."""
        due = self.now() if due is None else due
        shard = int(hashlib.sha256(task["id"].encode()).hexdigest(), 16) % self.settings.shards
        item = row(
            f"RUN#{task['id']}",
            h=task["PK"][2:],
            taskId=task["id"],
            status="PENDING",
            dueAt=due,
            GSI1PK=f"RUN#{shard}",
            GSI1SK=f"{due:020d}#{task['id']}",
        )
        if previous:
            item["rev"] = previous["rev"] + 1
        return item

    @staticmethod
    def done_intent(item: dict) -> dict:
        new = revised(item, status="DONE")
        new.pop("GSI1PK", None)
        new.pop("GSI1SK", None)
        return new

    def context(self, actor: str, household: str) -> Context:
        h = self.store.get("Domain", (hkey(household), "META"))
        member = self.store.get("Domain", (hkey(household), f"MEMBER#{actor}"))
        profile = self.store.get("Domain", (f"P#{actor}", "PROFILE"))
        if not h or not active(member, self.now()) or not active(profile, self.now()):
            raise denied()
        return Context(actor, h, member, profile)

    def personal(self, ctx: Context) -> None:
        if ctx.profile["kind"] != "personal":
            raise denied()

    def admin(self, ctx: Context) -> None:
        self.personal(ctx)
        if ctx.member["role"] != "admin":
            raise denied()

    def task_access(
        self, ctx: Context, task_id: str, permission: str = "read"
    ) -> tuple[dict, list[Change]]:
        task = self.store.get("Domain", (hkey(ctx.h), f"TASK#{task_id}"))
        if not task:
            raise missing()
        if ctx.profile["kind"] == "shared":
            if task["visibility"] != "household" or permission != "read":
                raise missing()
            return task, [guard("Domain", task)]
        if task["owner"] == ctx.actor:
            return task, [guard("Domain", task)]
        if permission == "read" and task["visibility"] == "household":
            return task, [guard("Domain", task)]
        if permission == "owner":
            raise missing()
        delegation = self.store.get("Domain", (hkey(ctx.h), f"DELEGATION#{task_id}#{ctx.actor}"))
        owner = self.store.get("Domain", (hkey(ctx.h), f"MEMBER#{task['owner']}"))
        if (
            not active(delegation, self.now())
            or not active(owner, self.now())
            or delegation.get("delegateEpoch", 1) != ctx.member.get("accessEpoch", 1)
            or delegation.get("ownerEpoch", 1) != owner.get("accessEpoch", 1)
            or permission not in delegation["permissions"]
        ):
            raise missing()
        return task, [guard("Domain", value) for value in (task, delegation, owner)]

    def event(
        self, ctx: Context, aggregate: str, version: int, *, wake: bool = False, kind: str = "task"
    ) -> Change:
        eid = uid()
        shard = int(hashlib.sha256(eid.encode()).hexdigest(), 16) % self.settings.shards
        envelope = dict(
            schemaVersion="1.0",
            eventId=eid,
            type=f"koyori.{kind}.changed.v1",
            occurredAt=self.now(),
            householdId=ctx.h,
            actorId=ctx.actor,
            aggregateId=aggregate,
            aggregateVersion=version,
            mode="sandbox",
            wake=wake,
        )
        return put(
            "Delivery",
            row(
                f"OUTBOX#{eid}",
                status="PENDING",
                envelope=envelope,
                GSI1PK=f"OUTBOX#{shard}",
                GSI1SK=f"{self.now():020d}#{eid}",
            ),
        )

    def _authorize(self, ctx: Context, auth: str, target: str | None) -> list[Change]:
        if auth == "admin":
            self.admin(ctx)
        elif auth == "personal":
            self.personal(ctx)
        elif auth in {"read", "control", "owner"}:
            return self.task_access(ctx, target, auth)[1]
        return []

    def _grant(self, ctx: Context, grant_id: str | None, operation: str, hashed: str) -> Change:
        grant = (
            self.store.get("Sessions", (f"GRANT#{digest({'id': grant_id})}", "META"))
            if grant_id
            else None
        )
        if (
            not active(grant, self.now())
            or grant.get("consumed")
            or (grant["actor"], grant["h"], grant["operation"], grant["requestHash"])
            != (ctx.actor, ctx.h, operation, hashed)
        ):
            raise Problem(
                403, "STEP_UP_REQUIRED", "Fresh authentication bound to this operation is required."
            )
        return put("Sessions", revised(grant, consumed=True), grant)

    def mutate(
        self,
        actor: str,
        h: str,
        operation: str,
        body: dict,
        key: str | None,
        version: int | None,
        grant: str | None,
        work,
        *,
        auth="personal",
        target=None,
    ) -> dict:
        key = idempotency_key(key)
        hashed = request_hash(body, version)
        ikey = (f"IDEMP#{digest({'p': actor, 'h': h, 'op': operation, 'key': key})}", "META")
        for _ in range(6):
            ctx = self.context(actor, h)
            checks = self._authorize(ctx, auth, target)
            cached = self.store.get("Sessions", ikey)
            if cached:
                if cached["requestHash"] != hashed:
                    raise Problem(
                        409,
                        "IDEMPOTENCY_CONFLICT",
                        "The idempotency key was used with different content.",
                    )
                return cached["response"]
            response, writes, expands = work(ctx)
            if expands:
                writes.append(self._grant(ctx, grant, operation, hashed))
            writes.append(
                put(
                    "Sessions",
                    row(
                        *ikey,
                        actor=actor,
                        requestHash=hashed,
                        response=response,
                        createdAt=self.now(),
                    ),
                )
            )
            try:
                self.store.transact(ctx.guards() + checks + writes)
                return response
            except Conflict:
                continue  # Re-read permissions as well as revisions; never retry blind writes.
        raise Problem(
            503, "CONTENTION", "Concurrent changes; retry with the same idempotency key.", True
        )

    def require_version(self, item: dict | None, version: int | None) -> None:
        if (item["rev"] if item else 0) != version:
            raise Problem(412, "REVISION_CONFLICT", "The resource revision has changed.")

    def create_household(self, actor: str, body: dict, key: str | None) -> dict:
        key = idempotency_key(key)
        ikey = (f"IDEMP#{digest({'p': actor, 'op': 'create_household', 'key': key})}", "META")
        for _ in range(6):
            profile = self.store.get("Domain", (f"P#{actor}", "PROFILE"))
            if profile and (profile["kind"] != "personal" or not active(profile, self.now())):
                raise denied()
            cached = self.store.get("Sessions", ikey)
            if cached:
                if cached["requestHash"] != digest(body):
                    raise Problem(
                        409, "IDEMPOTENCY_CONFLICT", "The key was used with different content."
                    )
                self.context(actor, cached["response"]["id"])
                return cached["response"]
            # Revoked discovery links remain as history; only current slots count.
            if profile and profile.get("householdCount", 0) >= 8:
                raise Problem(429, "HOUSEHOLD_LIMIT", "Principal household limit reached.")
            hid = uid()
            profile_new = (
                revised(profile, householdCount=profile.get("householdCount", 0) + 1)
                if profile
                else row(f"P#{actor}", "PROFILE", kind="personal", active=True, householdCount=1)
            )
            household = row(
                hkey(hid),
                id=hid,
                name=body["name"],
                timeZone=body["timeZone"],
                adminCount=1,
                memberCount=1,
                memberIds=[actor],
                activeTasks=0,
                createdAt=self.now(),
            )
            member = row(
                hkey(hid),
                f"MEMBER#{actor}",
                principalId=actor,
                role="admin",
                kind="personal",
                active=True,
                expiresAt=None,
                accessEpoch=1,
            )
            response = projection(household)
            changes = [
                put("Domain", profile_new, profile),
                put("Domain", household),
                put("Domain", member),
                put("Domain", row(f"P#{actor}", f"H#{hid}", householdId=hid)),
                put(
                    "Domain",
                    row(
                        hkey(hid),
                        "POLICY#synthetic",
                        id="synthetic",
                        capability="synthetic.checkpoint",
                        enabled=True,
                    ),
                ),
                put("Sessions", row(*ikey, requestHash=digest(body), response=response)),
            ]
            try:
                self.store.transact(changes)
                return response
            except Conflict:
                continue
        raise Problem(503, "CONTENTION", "Concurrent changes; retry.", True)

    def add_member(self, ctx: Context, body: dict) -> tuple[dict, list[Change], bool]:
        self.admin(ctx)
        principal = body["principalId"]
        if (
            body["kind"] == "shared"
            and body["role"] == "admin"
            or body["role"] == "admin"
            and body["expiresAt"] is not None
        ):
            raise Problem(
                422, "INVALID_MEMBER", "Administrators must be personal and non-expiring."
            )
        if body["expiresAt"] is not None and body["expiresAt"] <= self.now():
            raise Problem(422, "INVALID_EXPIRY", "Expiry must be in the future.")
        old = self.store.get("Domain", (hkey(ctx.h), f"MEMBER#{principal}"))
        if old and old["active"]:
            raise Problem(409, "MEMBER_EXISTS", "Membership already exists; amend or revoke it.")
        if ctx.household["memberCount"] >= self.settings.max_members:
            raise Problem(429, "MEMBER_LIMIT", "Household membership limit reached.")
        profile = self.store.get("Domain", (f"P#{principal}", "PROFILE"))
        if profile and profile["kind"] != body["kind"]:
            raise Problem(
                409, "PRINCIPAL_KIND_CONFLICT", "Principal kind cannot be changed by membership."
            )
        link = self.store.get("Domain", (f"P#{principal}", f"H#{ctx.h}"))
        member = row(
            hkey(ctx.h),
            f"MEMBER#{principal}",
            **{k: v for k, v in body.items() if k != "schemaVersion"},
            active=True,
            accessEpoch=old.get("accessEpoch", 1) + 1 if old else 1,
        )
        if old:
            member["rev"] = old["rev"] + 1
        household = revised(
            ctx.household,
            memberCount=ctx.household["memberCount"] + 1,
            memberIds=[*ctx.household.get("memberIds", [ctx.actor]), principal],
            adminCount=ctx.household["adminCount"] + int(body["role"] == "admin"),
        )
        changes = [
            put("Domain", member, old),
            put("Domain", household, ctx.household),
            self.event(ctx, principal, member["rev"], kind="access"),
        ]
        if not link or not link.get("active", True):
            if profile and profile.get("householdCount", 0) >= 8:
                raise Problem(429, "HOUSEHOLD_LIMIT", "Principal household limit reached.")
            changes.append(
                put(
                    "Domain",
                    revised(link, active=True)
                    if link
                    else row(f"P#{principal}", f"H#{ctx.h}", householdId=ctx.h),
                    link,
                )
            )
            changes.append(
                put(
                    "Domain",
                    revised(profile, householdCount=profile.get("householdCount", 0) + 1)
                    if profile
                    else row(
                        f"P#{principal}",
                        "PROFILE",
                        kind=body["kind"],
                        active=True,
                        householdCount=1,
                    ),
                    profile,
                )
            )
        elif profile:
            changes.append(guard("Domain", profile))
        return projection(member), changes, True

    def change_member(
        self, ctx: Context, principal: str, body: dict, version: int, *, revoke: bool
    ) -> tuple[dict, list[Change], bool]:
        self.admin(ctx)
        old = self.store.get("Domain", (hkey(ctx.h), f"MEMBER#{principal}"))
        if not old or not old["active"]:
            raise missing()
        self.require_version(old, version)
        role = body.get("role") or old["role"]
        expires = body.get("expiresAt", old["expiresAt"])
        if not revoke and (
            role == "admin"
            and (old["kind"] == "shared" or expires is not None)
            or expires is not None
            and expires <= self.now()
        ):
            raise Problem(422, "INVALID_MEMBER", "Administrator or expiry conditions are invalid.")
        admin_delta = int(not revoke and role == "admin") - int(old["role"] == "admin")
        if ctx.household["adminCount"] + admin_delta < 1:
            raise Problem(409, "LAST_ADMIN", "At least one administrator must remain.")
        member = revised(
            old,
            role=role,
            expiresAt=expires,
            active=not revoke,
            accessEpoch=old.get("accessEpoch", 1) + int(revoke or not active(old, self.now())),
        )
        household = revised(
            ctx.household,
            adminCount=ctx.household["adminCount"] + admin_delta,
            memberCount=ctx.household["memberCount"] - int(revoke),
            memberIds=[p for p in ctx.household.get("memberIds", [ctx.actor]) if p != principal]
            if revoke
            else ctx.household.get("memberIds", [ctx.actor]),
        )
        changes = [
            put("Domain", member, old),
            put("Domain", household, ctx.household),
            self.event(ctx, principal, member["rev"], kind="access"),
        ]
        if revoke:
            profile = self.store.get("Domain", (f"P#{principal}", "PROFILE"))
            link = self.store.get("Domain", (f"P#{principal}", f"H#{ctx.h}"))
            changes.extend(
                [
                    put(
                        "Domain",
                        revised(profile, householdCount=profile["householdCount"] - 1),
                        profile,
                    ),
                    put("Domain", revised(link, active=False), link),
                ]
            )
        return (
            projection(member),
            changes,
            not revoke
            and (
                admin_delta > 0
                or not active(old, self.now())
                or old["expiresAt"] is not None
                and (expires is None or expires > old["expiresAt"])
            ),
        )

    def command(self, ctx: Context, body: dict) -> tuple[dict, list[Change], bool]:
        self.personal(ctx)
        policy = self.store.get("Domain", (hkey(ctx.h), "POLICY#synthetic"))
        if not policy or not policy["enabled"]:
            raise Problem(403, "POLICY_DENIED", "Synthetic execution is disabled.")
        if ctx.household["activeTasks"] >= self.settings.max_tasks:
            raise Problem(429, "TASK_LIMIT", "Active task limit reached.")
        tid, cid = uid(), uid()
        task = row(
            hkey(ctx.h),
            f"TASK#{tid}",
            id=tid,
            commandId=cid,
            owner=ctx.actor,
            label=body["label"],
            operation=body["operation"],
            visibility=body["visibility"],
            status="READY",
            mode="sandbox",
            result=None,
            checkpoint=0,
            wakeSeq=0,
            handledWake=0,
            runEpoch=0,
            leaseOwner=None,
            leaseUntil=0,
            createdAt=self.now(),
            updatedAt=self.now(),
            executionAuthorized=True,
            grantEpoch=ctx.member.get("accessEpoch", 1),
        )
        household = revised(ctx.household, activeTasks=ctx.household["activeTasks"] + 1)
        writes = [
            put("Domain", task),
            put("Delivery", self.run_intent(task, None)),
            put("Domain", household, ctx.household),
            guard("Domain", policy),
            put(
                "Domain",
                row(
                    hkey(ctx.h),
                    f"COMMAND#{cid}",
                    taskId=tid,
                    operation=body["operation"],
                    actor=ctx.actor,
                    acceptedAt=self.now(),
                ),
            ),
            put(
                "Domain",
                row(
                    hkey(ctx.h),
                    f"DECISION#{cid}",
                    taskId=tid,
                    policyRevision=policy["rev"],
                    decision="PERMITTED",
                    capability=body["operation"],
                    mode="sandbox",
                ),
            ),
            self.event(ctx, tid, 1, wake=True),
        ]
        return (
            dict(
                schemaVersion="1.0",
                commandId=cid,
                taskId=tid,
                acceptanceStatus="ACCEPTED",
                taskVersion=1,
                mode="sandbox",
                statusUrl=f"/v1/tasks/{tid}",
            ),
            writes,
            body["visibility"] == "household",
        )

    def change_task(
        self, ctx: Context, tid: str, body: dict, version: int, action: str
    ) -> tuple[dict, list[Change], bool]:
        task, checks = self.task_access(ctx, tid, "control")
        self.require_version(task, version)
        if task["status"] in TERMINAL:
            raise Problem(409, "TASK_TERMINAL", "Terminal tasks cannot be changed.")
        expands = False
        values = dict(
            updatedAt=self.now(), leaseOwner=None, leaseUntil=0, runEpoch=task["runEpoch"] + 1
        )
        wake = False
        if action == "amend":
            if not any(body.get(k) is not None for k in ("label", "visibility")):
                raise Problem(422, "EMPTY_PATCH", "Provide a label or visibility.")
            if body.get("visibility") is not None:
                self.task_access(ctx, tid, "owner")
                values["visibility"] = body["visibility"]
                expands = body["visibility"] == "household" and task["visibility"] != "household"
            if body.get("label") is not None:
                values["label"] = body["label"]
            values["status"] = "PAUSED" if task["status"] == "PAUSED" else "READY"
            wake = values["status"] == "READY"
        elif action == "pause":
            if task["status"] == "PAUSED":
                raise Problem(409, "INVALID_TRANSITION", "Task is already paused.")
            values["status"] = "PAUSED"
        elif action == "resume":
            if task["status"] != "PAUSED":
                raise Problem(409, "INVALID_TRANSITION", "Only a paused task can resume.")
            policy = self.store.get("Domain", (hkey(ctx.h), "POLICY#synthetic"))
            owner = self.store.get("Domain", (hkey(ctx.h), f"MEMBER#{task['owner']}"))
            if (
                not active(owner, self.now())
                or task.get("grantEpoch", 1) != owner.get("accessEpoch", 1)
                or not policy
                or not policy["enabled"]
            ):
                raise Problem(403, "POLICY_DENIED", "Current authority does not permit execution.")
            checks.extend([guard("Domain", policy), guard("Domain", owner)])
            values["status"], wake = "READY", True
        elif action == "cancel":
            values["status"] = "CANCELLED"
        else:
            raise ValueError("Unknown task transition")
        new = revised(task, **values)
        writes = checks + [put("Domain", new, task), self.event(ctx, tid, new["rev"], wake=wake)]
        intent = self.store.get("Delivery", (f"RUN#{tid}", "META"))
        if new["status"] == "READY":
            writes.append(put("Delivery", self.run_intent(new, intent), intent))
        elif intent:
            writes.append(put("Delivery", self.done_intent(intent), intent))
        if action == "cancel":
            writes.append(
                put(
                    "Domain",
                    revised(ctx.household, activeTasks=ctx.household["activeTasks"] - 1),
                    ctx.household,
                )
            )
        return projection(new), writes, expands

    def delegate(self, ctx: Context, tid: str, body: dict) -> tuple[dict, list[Change], bool]:
        self.task_access(ctx, tid, "owner")
        target = self.store.get("Domain", (hkey(ctx.h), f"MEMBER#{body['principalId']}"))
        if (
            not active(target, self.now())
            or target["kind"] != "personal"
            or body["principalId"] == ctx.actor
        ):
            raise Problem(
                422, "INVALID_DELEGATE", "Delegate must be another current personal member."
            )
        if not self.now() < body["expiresAt"] <= self.now() + 30 * 86400:
            raise Problem(422, "INVALID_EXPIRY", "Delegation expires within thirty days.")
        dkey = (hkey(ctx.h), f"DELEGATION#{tid}#{body['principalId']}")
        old = self.store.get("Domain", dkey)
        if active(old, self.now()):
            raise Problem(
                409, "DELEGATION_EXISTS", "Revoke the previous delegation before replacing it."
            )
        item = row(
            *dkey,
            id=body["principalId"],
            taskId=tid,
            owner=ctx.actor,
            permissions=body["permissions"],
            expiresAt=body["expiresAt"],
            active=True,
            delegateEpoch=target.get("accessEpoch", 1),
            ownerEpoch=ctx.member.get("accessEpoch", 1),
        )
        if old:
            item["rev"] = old["rev"] + 1
        return (
            projection(item),
            [
                put("Domain", item, old),
                guard("Domain", target),
                self.event(ctx, tid, self.task_access(ctx, tid)[0]["rev"]),
            ],
            True,
        )

    def revoke_delegation(
        self, ctx: Context, tid: str, did: str, version: int
    ) -> tuple[dict, list[Change], bool]:
        self.task_access(ctx, tid, "owner")
        item = self.store.get("Domain", (hkey(ctx.h), f"DELEGATION#{tid}#{did}"))
        if not item or not item["active"]:
            raise missing()
        self.require_version(item, version)
        new = revised(item, active=False)
        return (
            projection(new),
            [put("Domain", new, item), self.event(ctx, tid, self.task_access(ctx, tid)[0]["rev"])],
            False,
        )

    def policy(
        self, ctx: Context, pid: str, body: dict, version: int
    ) -> tuple[dict, list[Change], bool]:
        self.admin(ctx)
        if pid != "synthetic":
            raise missing()
        old = self.store.get("Domain", (hkey(ctx.h), "POLICY#synthetic"))
        self.require_version(old, version)
        new = revised(old, enabled=body["enabled"])
        return (
            projection(new),
            [put("Domain", new, old), self.event(ctx, pid, new["rev"], kind="policy")],
            body["enabled"] and not old["enabled"],
        )

    def challenge(self, actor: str, h: str, body: dict, key: str | None) -> dict:
        def work(ctx):
            cid, nonce = uid(), secrets.token_urlsafe(32)
            record = row(
                f"CHALLENGE#{cid}",
                actor=actor,
                h=h,
                operation=body["operation"],
                requestHash=body["requestHash"],
                nonce=nonce,
                createdAt=self.now(),
                expiresAt=self.now() + 180,
                active=True,
                consumed=False,
            )
            return (
                dict(
                    id=cid,
                    nonce=nonce,
                    expiresAt=record["expiresAt"],
                    issuer=self.settings.issuer,
                    clientId=self.settings.client_id,
                ),
                [put("Sessions", record)],
                False,
            )

        return self.mutate(actor, h, "POST /v1/auth/step-up", body, key, None, None, work)

    def complete_challenge(
        self, actor: str, h: str, cid: str, body: dict, key: str | None, tokens
    ) -> dict:
        claims = tokens.verify(body["identityProof"], identity=True)

        def work(ctx):
            item = self.store.get("Sessions", (f"CHALLENGE#{cid}", "META"))
            if (
                not active(item, self.now())
                or item["consumed"]
                or (item["actor"], item["h"]) != (actor, h)
            ):
                raise Problem(403, "CHALLENGE_INVALID", "Authentication challenge is unavailable.")
            if (
                claims["sub"] != actor
                or claims.get("nonce") != item["nonce"]
                or not item["createdAt"] <= claims["auth_time"] <= self.now() + 5
            ):
                raise Problem(
                    403,
                    "AUTHENTICATION_NOT_FRESH",
                    "Proof must match the principal, nonce and fresh authentication.",
                )
            gid = secrets.token_urlsafe(32)
            grant = row(
                f"GRANT#{digest({'id': gid})}",
                actor=actor,
                h=h,
                operation=item["operation"],
                requestHash=item["requestHash"],
                expiresAt=self.now() + 120,
                active=True,
                consumed=False,
            )
            return (
                dict(grant=gid, expiresAt=grant["expiresAt"]),
                [put("Sessions", grant), put("Sessions", revised(item, consumed=True), item)],
                False,
            )

        # Store only a proof hash in the idempotency record, never the JWT.
        return self.mutate(
            actor,
            h,
            f"POST /v1/auth/step-up/{cid}/complete",
            {"proofHash": digest(body)},
            key,
            None,
            None,
            work,
        )

    def page(
        self,
        ctx: Context,
        table: str,
        prefix: str,
        route: str,
        cursor: str | None,
        *,
        pk=None,
        authorize=None,
    ) -> dict:
        after = self.cursors.decode(cursor, ctx.actor, ctx.h, route)
        records, last = self.store.query(
            table, pk or hkey(ctx.h), prefix=prefix, after=after, limit=50
        )
        items = []
        for record in records:
            try:
                if authorize:
                    record = authorize(record)
                if record is not None:
                    items.append(projection(record))
            except Problem as exc:
                if exc.status != 404:
                    raise
        response = dict(
            items=items,
            nextCursor=self.cursors.encode(ctx.actor, ctx.h, route, last) if last else None,
        )
        if route == "activity":
            # Catch-up must retain a bookmark even at the current end of the feed.
            key = {"PK": records[-1]["PK"], "SK": records[-1]["SK"]} if records else after
            response["resumeCursor"] = (
                self.cursors.encode(ctx.actor, ctx.h, route, key) if key else None
            )
        return response
