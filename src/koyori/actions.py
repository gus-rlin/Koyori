"""Deterministic authorization and durable simulated commerce operations.

DISPATCHING is persisted before a provider call. A crash/timeout enters reconciliation;
the budget stays held until provider evidence establishes the outcome.
"""

import hashlib
import hmac
import json
import secrets

from koyori.domain import active, hkey, projection, row, uid
from koyori.errors import Conflict, Problem, missing
from koyori.security import digest
from koyori.stage2 import Service
from koyori.store import guard, put, revised

CATALOG = {"milk": 180, "bread": 250, "fruit": 400, "vegetarian-meal": 1400, "chicken-meal": 1600}
CAPABILITIES = (
    {
        "id": "commerce.groceries",
        "rev": 1,
        "access": "write",
        "provider": "commerce-simulator",
        "mode": "simulated",
        "proof": "provider operation and order identifiers, exact conditions, integer total",
        "timeoutSeconds": 10,
        "retry": "reconcile by stable provider key; never blind retry",
    },
    {
        "id": "commerce.meals",
        "rev": 1,
        "access": "write",
        "provider": "commerce-simulator",
        "mode": "simulated",
        "proof": "provider operation and order identifiers, exact conditions, integer total",
        "timeoutSeconds": 10,
        "retry": "reconcile by stable provider key; never blind retry",
    },
    {
        "id": "calendar.read",
        "rev": 1,
        "access": "read",
        "provider": "google-calendar",
        "mode": "real",
        "proof": "selected-calendar API response and synchronization token",
        "timeoutSeconds": 10,
        "retry": "bounded page fetch and sync-token reset",
    },
)


class UnknownOutcome(Exception):
    """Provider accepted the call but the response is unavailable."""


class Simulator(Service):
    """Persistent fixture provider. No client option can turn it into a real merchant."""

    def catalog(self):
        return self.store.get("Domain", ("PROVIDER#commerce-simulator", "META")) or row(
            "PROVIDER#commerce-simulator", prices=CATALOG, fault="none"
        )

    def price(self, body):
        catalog = self.catalog()
        total = sum(catalog["prices"][line["sku"]] * line["quantity"] for line in body["lines"])
        return total, catalog

    def lookup(self, action):
        item = self.store.get("Domain", (f"SIMOP#{action['providerKey']}", "META"))
        if item and item["conditionsHash"] != action["conditionsHash"]:
            raise Problem(409, "PROVIDER_KEY_CONFLICT", "Provider key content differs.")
        return item["receipt"] if item else None

    def execute(self, action):
        existing = self.lookup(action)
        if existing:
            return existing
        terms = action["conditions"]
        order_key = (f"SIMORDER#{action['businessId']}", "META")
        for _ in range(6):
            catalog = self.catalog()
            existing = self.lookup(action)
            if existing:
                return existing
            order = self.store.get("Domain", order_key)
            expected = action["providerVersion"]
            valid = (order["rev"] if order else 0) == expected
            valid = valid and (not order or order["status"] == "CONFIRMED")
            valid = valid and (
                terms["operation"] == "cancel" or catalog["prices"] == terms["prices"]
            )
            valid = valid and terms["deliveryAt"] > self.domain.now()
            status = (
                ("CANCELLED" if terms["operation"] == "cancel" else "CONFIRMED")
                if valid
                else "REJECTED"
            )
            receipt = {
                "kind": "simulated",
                "provider": "commerce-simulator",
                "operationId": action["providerKey"],
                "orderId": action["businessId"],
                "status": status,
                "conditionsHash": action["conditionsHash"],
                "currency": "EUR",
                "totalMinor": terms["totalMinor"] if valid else 0,
                "providerVersion": expected + 1 if valid else expected,
                "observedAt": self.domain.now(),
            }
            writes = [
                put(
                    "Domain",
                    row(
                        f"SIMOP#{action['providerKey']}",
                        conditionsHash=action["conditionsHash"],
                        receipt=receipt,
                    ),
                )
            ]
            if valid:
                new = row(
                    *order_key,
                    rev=expected + 1,
                    status=status,
                    totalMinor=terms["totalMinor"],
                    lines=terms["lines"],
                    deliveryAt=terms["deliveryAt"],
                    mode="simulated",
                )
                writes.append(put("Domain", new, order))
            elif order:
                writes.append(guard("Domain", order))
            actual_catalog = self.store.get("Domain", ("PROVIDER#commerce-simulator", "META"))
            if actual_catalog and actual_catalog["rev"] != catalog["rev"]:
                continue
            if actual_catalog:
                writes.append(guard("Domain", actual_catalog))
            else:
                from koyori.store import Change

                writes.append(Change("Domain", ("PROVIDER#commerce-simulator", "META"), None))
            try:
                self.store.transact(writes)
                if catalog.get("fault") == "timeout-after-commit":
                    raise UnknownOutcome
                return receipt
            except Conflict:
                continue
        raise UnknownOutcome


class Actions(Service):
    def __init__(self, domain, provider=None):
        super().__init__(domain)
        self.provider = provider or Simulator(domain)

    def get(self, ctx, category, identifier, *, inactive=True):
        item = self.store.get("Domain", (hkey(ctx.h), f"{category}#{identifier}"))
        if not item or ctx.profile["kind"] != "personal" or item["owner"] != ctx.actor:
            raise missing()
        if not inactive and not active(item, self.domain.now()):
            raise Problem(409, "CONNECTION_REVOKED", "Connection is unavailable.")
        return item

    def connection(self, ctx):
        identifier = uid()
        item = row(
            hkey(ctx.h),
            f"CONNECTION#{identifier}",
            id=identifier,
            owner=ctx.actor,
            provider="commerce-simulator",
            mode="simulated",
            active=True,
            epoch=1,
            memberEpoch=ctx.member.get("accessEpoch", 1),
            capabilities=["commerce.groceries", "commerce.meals"],
            createdAt=self.domain.now(),
        )
        from koyori.calendar import Envelope

        webhook = row(
            f"H#{ctx.h}#OWNER#{ctx.actor}",
            f"WEBHOOK#{identifier}",
            envelope=Envelope(self.domain.settings).seal(
                {"secret": secrets.token_hex(32)}, ctx.actor, identifier
            ),
        )
        return (
            {"id": identifier, "rev": 1},
            [put("Domain", item), put("Connections", webhook)],
            False,
        )

    def notification_signature(self, action, payload):
        """Fixture-provider signing helper; the secret never enters the public API."""
        from koyori.calendar import Envelope

        secret_row = self.store.get(
            "Connections",
            (f"H#{action['PK'][2:]}#OWNER#{action['owner']}", f"WEBHOOK#{action['connectionId']}"),
        )
        secret = Envelope(self.domain.settings).open(
            secret_row["envelope"], action["owner"], action["connectionId"]
        )["secret"]
        return hmac.new(
            secret.encode(),
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(),
            hashlib.sha256,
        ).hexdigest()

    def notify(self, payload, signature):
        action = self.store.get(
            "Domain", (hkey(payload["householdId"]), f"ACTION#{payload['actionId']}")
        )
        if (
            not action
            or not signature
            or not hmac.compare_digest(self.notification_signature(action, payload), signature)
        ):
            raise Problem(403, "WEBHOOK_INVALID", "Provider notification signature is invalid.")
        if abs(self.domain.now() - payload["occurredAt"]) > 300:
            raise Problem(
                403, "WEBHOOK_EXPIRED", "Provider notification is outside the replay window."
            )
        inbox_key = (f"INBOX#commerce-simulator#{payload['eventId']}", "META")
        if self.store.get("Delivery", inbox_key):
            return
        writes = [
            guard("Domain", action),
            put("Delivery", row(*inbox_key, receivedAt=self.domain.now())),
        ]
        if action["status"] in {"DISPATCHING", "UNKNOWN"}:
            intent = self.store.get("Delivery", (f"ACTIONRUN#{action['id']}", "META"))
            writes.append(put("Delivery", self.intent(action, intent), intent))
        self.store.transact(writes)

    def revoke(self, ctx, cid, version):
        old = self.get(ctx, "CONNECTION", cid)
        self.domain.require_version(old, version)
        new = revised(old, active=False, epoch=old["epoch"] + 1)
        return (
            {"id": cid, "rev": new["rev"]},
            [
                put("Domain", new, old),
                self.domain.event(ctx, cid, new["rev"], kind="connection", mode="simulated"),
            ],
            False,
        )

    def budget(self, ctx):
        self.domain.personal(ctx)
        return self.store.get("Domain", (hkey(ctx.h), f"BUDGET#{ctx.actor}"))

    def configure_budget(self, ctx, body, version):
        old = self.budget(ctx)
        self.domain.require_version(old, version)
        used = old["spentMinor"] + old["heldMinor"] if old else 0
        if body["limitMinor"] < used:
            raise Problem(409, "BUDGET_COMMITTED", "Limit is below committed and reserved funds.")
        item = row(
            hkey(ctx.h),
            f"BUDGET#{ctx.actor}",
            rev=old["rev"] + 1 if old else 1,
            id=ctx.actor,
            owner=ctx.actor,
            **{k: v for k, v in body.items() if k != "schemaVersion"},
            spentMinor=old["spentMinor"] if old else 0,
            heldMinor=old["heldMinor"] if old else 0,
            policyEpoch=old["policyEpoch"] + 1 if old else 1,
        )
        expands = (
            not old
            or body["limitMinor"] > old["limitMinor"]
            or body["perActionMinor"] > old["perActionMinor"]
            or body["enabled"]
            and not old["enabled"]
            or not body["approvalRequired"]
            and old["approvalRequired"]
        )
        return {"id": ctx.actor, "rev": item["rev"]}, [put("Domain", item, old)], expands

    def quote(self, ctx, body, *, reuse_unexecuted=False):
        connection = self.get(ctx, "CONNECTION", body["connectionId"], inactive=False)
        if connection["provider"] != "commerce-simulator" or connection["mode"] != "simulated":
            raise Problem(409, "CAPABILITY_UNAVAILABLE", "No qualified merchant configured.")
        if body["capability"] not in connection["capabilities"]:
            raise Problem(403, "CAPABILITY_DENIED", "Connection lacks the capability.")
        if body["deliveryAt"] <= self.domain.now():
            raise Problem(422, "INVALID_TIME", "Delivery must be in the future.")
        meals = {"vegetarian-meal", "chicken-meal"}
        if any(
            (line["sku"] in meals) != (body["capability"] == "commerce.meals")
            for line in body["lines"]
        ):
            raise Problem(422, "INVALID_LINES", "Lines do not match the capability.")
        target = None
        business = self.store.get(
            "Domain", (hkey(ctx.h), f"BUSINESS#{ctx.actor}#{body['intentionId']}")
        )
        if body["operation"] == "create":
            retry = bool(
                reuse_unexecuted
                and business
                and business["status"] in {"BLOCKED", "REJECTED"}
                and business["providerVersion"] == 0
                and business["totalMinor"] == 0
                and not business["actionId"]
            )
            if business and not retry:
                raise Problem(409, "INTENTION_EXISTS", "This commercial intention already exists.")
            business_id, previous, provider_version = business["id"] if retry else uid(), 0, 0
        else:
            target = self.get(ctx, "ACTION", body["targetActionId"])
            if (
                target["status"] != "CONFIRMED"
                or target["connectionId"] != connection["id"]
                or target["intentionId"] != body["intentionId"]
                or target["capability"] != body["capability"]
                or not business
                or business["status"] != "CONFIRMED"
                or business["actionId"] != target["id"]
            ):
                raise Problem(409, "TARGET_UNRESOLVED", "Reconcile the current operation first.")
            business_id, previous, provider_version = (
                business["id"],
                business["totalMinor"],
                business["providerVersion"],
            )
        total, catalog = self.provider.price(body)
        conditions = {
            k: body[k] for k in ("capability", "intentionId", "operation", "lines", "deliveryAt")
        }
        conditions.update(
            totalMinor=total,
            currency="EUR",
            prices=catalog["prices"],
            connectionId=connection["id"],
            connectionEpoch=connection["epoch"],
            businessId=business_id,
            previousTotal=previous,
            providerVersion=provider_version,
            mode="simulated",
        )
        if body["operation"] == "create" and business:
            conditions["retryBusinessRevision"] = business["rev"]
        identifier = uid()
        item = row(
            hkey(ctx.h),
            f"QUOTE#{identifier}",
            id=identifier,
            owner=ctx.actor,
            conditions=conditions,
            conditionsHash=digest(conditions),
            createdAt=self.domain.now(),
            expiresAt=self.domain.now() + 120,
            mode="simulated",
        )
        writes = [put("Domain", item), guard("Domain", connection)]
        if business:
            writes.append(guard("Domain", business))
        if target:
            writes.append(guard("Domain", target))
        return {"id": identifier, "rev": 1}, writes, False

    def current_quote(self, ctx, qid):
        quote = self.get(ctx, "QUOTE", qid)
        if quote["expiresAt"] <= self.domain.now():
            raise Problem(409, "QUOTE_EXPIRED", "Request a fresh quote.")
        conditions = quote["conditions"]
        connection = self.get(ctx, "CONNECTION", conditions["connectionId"], inactive=False)
        if connection["epoch"] != conditions["connectionEpoch"]:
            raise Problem(409, "QUOTE_CHANGED", "Connection authority changed.")
        _, catalog = self.provider.price(conditions)
        if (
            conditions["prices"] != catalog["prices"]
            or conditions["deliveryAt"] <= self.domain.now()
        ):
            raise Problem(409, "QUOTE_CHANGED", "Provider conditions have changed.")
        return quote, connection

    def approve(self, ctx, qid):
        quote, connection = self.current_quote(ctx, qid)
        budget = self.budget(ctx)
        if not budget or not budget["enabled"]:
            raise Problem(403, "POLICY_DENIED", "Configure an enabled budget first.")
        aid = uid()
        item = row(
            hkey(ctx.h),
            f"APPROVAL#{aid}",
            id=aid,
            owner=ctx.actor,
            quoteId=qid,
            conditionsHash=quote["conditionsHash"],
            policyEpoch=budget["policyEpoch"],
            memberEpoch=ctx.member.get("accessEpoch", 1),
            consumed=False,
            expiresAt=quote["expiresAt"],
        )
        return (
            {"id": aid, "rev": 1},
            [
                put("Domain", item),
                guard("Domain", quote),
                guard("Domain", connection),
                guard("Domain", budget),
            ],
            True,
        )

    def intent(self, action, old=None, due=None):
        due = self.domain.now() if due is None else due
        return row(
            f"ACTIONRUN#{action['id']}",
            rev=old["rev"] + 1 if old else 1,
            h=action["PK"][2:],
            actionId=action["id"],
            status="PENDING",
            dueAt=due,
            GSI1PK=f"ACTIONRUN#{int(action['id'][:8], 16) % self.domain.settings.shards}",
            GSI1SK=f"{due:020d}#{action['id']}",
        )

    def reserve(self, ctx, body, *, goal_run=None):
        quote, connection = self.current_quote(ctx, body["quoteId"])
        goal = None
        cancellation = False
        if quote.get("goalId"):
            goal = self.store.get("Domain", (hkey(ctx.h), f"TASK#{quote['goalId']}"))
            if (
                not goal_run
                or not goal
                or goal["runEpoch"] != goal_run["runEpoch"]
                or goal["leaseOwner"] != goal_run["leaseOwner"]
                or goal["leaseUntil"] <= self.domain.now()
            ):
                raise Problem(
                    409, "GOAL_CONTROL_REQUIRED", "This quote is executed by its current goal run."
                )
            cancellation = bool(quote.get("goalCancellation") and goal.get("cancelRequested"))
            if goal["dispatchEpoch"] != quote["goalEpoch"] or goal["status"] != (
                "CANCELLING" if cancellation else "RUNNING"
            ):
                raise Problem(409, "GOAL_CHANGED", "Goal conditions changed before reservation.")
        terms = quote["conditions"]
        budget = self.budget(ctx)
        if (
            not budget
            or (not budget["enabled"] and not cancellation)
            or terms["totalMinor"] > budget["perActionMinor"]
        ):
            raise Problem(403, "POLICY_DENIED", "Action exceeds the current policy.")
        approval = None
        if budget["approvalRequired"] and not cancellation:
            if not body.get("approvalId"):
                raise Problem(403, "APPROVAL_REQUIRED", "Approve the exact quote first.")
            approval = self.get(ctx, "APPROVAL", body["approvalId"])
            if (
                approval["consumed"]
                or approval["expiresAt"] <= self.domain.now()
                or approval["conditionsHash"] != quote["conditionsHash"]
                or approval["quoteId"] != quote["id"]
                or approval["policyEpoch"] != budget["policyEpoch"]
                or approval["memberEpoch"] != ctx.member.get("accessEpoch", 1)
            ):
                raise Problem(
                    409, "APPROVAL_STALE", "The approval no longer matches current conditions."
                )
        business_key = (hkey(ctx.h), f"BUSINESS#{ctx.actor}#{terms['intentionId']}")
        business = self.store.get("Domain", business_key)
        retry = bool(
            business
            and terms.get("retryBusinessRevision") == business["rev"]
            and business["status"] in {"BLOCKED", "REJECTED"}
            and business["providerVersion"] == 0
            and not business["actionId"]
            and business["totalMinor"] == 0
        )
        if (terms["operation"] == "create" and business and not retry) or (
            terms["operation"] != "create"
            and (
                not business
                or business["status"] != "CONFIRMED"
                or business["providerVersion"] != terms["providerVersion"]
                or business["totalMinor"] != terms["previousTotal"]
            )
        ):
            raise Problem(409, "INTENTION_CONFLICT", "Commercial intention has changed.")
        held = max(0, terms["totalMinor"] - terms["previousTotal"])
        if budget["heldMinor"] + budget["spentMinor"] + held > budget["limitMinor"]:
            raise Problem(409, "BUDGET_EXCEEDED", "Insufficient available budget.")
        aid = uid()
        action = row(
            hkey(ctx.h),
            f"ACTION#{aid}",
            id=aid,
            owner=ctx.actor,
            visibility="private",
            intentionId=terms["intentionId"],
            businessId=terms["businessId"],
            capability=terms["capability"],
            connectionId=connection["id"],
            connectionEpoch=connection["epoch"],
            memberEpoch=ctx.member.get("accessEpoch", 1),
            policyEpoch=budget["policyEpoch"],
            providerVersion=terms["providerVersion"],
            previousActionId=business["actionId"] if business else None,
            quoteExpiresAt=quote["expiresAt"],
            conditions=terms,
            conditionsHash=quote["conditionsHash"],
            providerKey=aid,
            heldMinor=held,
            status="READY",
            mode="simulated",
            receipt=None,
            runEpoch=0,
            leaseUntil=0,
            createdAt=self.domain.now(),
            dueAt=self.domain.now(),
        )
        new_business = row(
            *business_key,
            rev=business["rev"] + 1 if business else 1,
            id=terms["businessId"],
            owner=ctx.actor,
            actionId=aid,
            status="PENDING",
            totalMinor=terms["previousTotal"],
            providerVersion=terms["providerVersion"],
        )
        writes = [
            put("Domain", action),
            put("Domain", new_business, business),
            put("Domain", revised(budget, heldMinor=budget["heldMinor"] + held), budget),
            guard("Domain", quote),
            guard("Domain", connection),
            put("Delivery", self.intent(action)),
            self.domain.event(ctx, aid, 1, kind="action", mode="simulated"),
        ]
        if goal:
            action.update(
                goalId=goal["id"],
                goalEpoch=goal["dispatchEpoch"],
                goalStep=quote["goalStep"],
                goalCancellation=cancellation,
            )
            writes.append(guard("Domain", goal))
            if not cancellation:
                from koyori.goals import validate_goal_sources

                writes.extend(validate_goal_sources(self.domain, ctx, goal))
        if approval:
            writes.append(put("Domain", revised(approval, consumed=True), approval))
        return {"id": aid, "rev": 1, "status": "READY"}, writes, False

    def _finish(self, action, receipt):
        for _ in range(6):
            current = self.store.get("Domain", (action["PK"], action["SK"]))
            if not current or current["status"] in {
                "CONFIRMED",
                "CANCELLED",
                "REJECTED",
                "BLOCKED",
            }:
                return
            if current["runEpoch"] != action["runEpoch"]:
                return
            # A provider announcement is not evidence: compare every authorized invariant.
            terms = current["conditions"]
            if (
                receipt["kind"] != "simulated"
                or receipt["operationId"] != current["providerKey"]
                or receipt["conditionsHash"] != current["conditionsHash"]
                or receipt["orderId"] != current["businessId"]
                or receipt["currency"] != "EUR"
                or receipt["status"] not in {"CONFIRMED", "CANCELLED", "REJECTED"}
                or receipt["status"] != "REJECTED"
                and (
                    receipt["totalMinor"] != terms["totalMinor"]
                    or receipt["providerVersion"] != current["providerVersion"] + 1
                    or (receipt["status"] == "CANCELLED") != (terms["operation"] == "cancel")
                )
            ):
                raise Problem(
                    502,
                    "INVALID_RECEIPT",
                    "Provider evidence does not match the authorized operation.",
                )
            budget = self.store.get("Domain", (action["PK"], f"BUDGET#{current['owner']}"))
            business = self.store.get(
                "Domain", (action["PK"], f"BUSINESS#{current['owner']}#{current['intentionId']}")
            )
            intent = self.store.get("Delivery", (f"ACTIONRUN#{current['id']}", "META"))
            confirmed = receipt["status"] != "REJECTED"
            delta = terms["totalMinor"] - terms["previousTotal"] if confirmed else 0
            new = revised(
                current, status=receipt["status"], receipt=receipt, heldMinor=0, leaseUntil=0
            )
            writes = [
                put("Domain", new, current),
                put(
                    "Domain",
                    revised(
                        budget,
                        heldMinor=budget["heldMinor"] - current["heldMinor"],
                        spentMinor=budget["spentMinor"] + delta,
                    ),
                    budget,
                ),
                put(
                    "Domain",
                    revised(
                        business,
                        status=receipt["status"]
                        if confirmed
                        else ("CONFIRMED" if terms["operation"] != "create" else "REJECTED"),
                        totalMinor=terms["totalMinor"] if confirmed else terms["previousTotal"],
                        providerVersion=receipt["providerVersion"]
                        if confirmed
                        else current["providerVersion"],
                        actionId=current["id"] if confirmed else current["previousActionId"],
                    ),
                    business,
                ),
            ]
            if intent:
                writes.append(put("Delivery", self.domain.done_intent(intent), intent))
            # Context may be revoked, yet financial reconciliation must still complete.
            from koyori.domain import Context

            ctx = Context(current["owner"], {"id": action["PK"][2:]}, {}, {})
            writes.append(
                self.domain.event(ctx, current["id"], new["rev"], kind="action", mode="simulated")
            )
            try:
                self.store.transact(writes)
                return
            except Conflict:
                continue
        raise Conflict("Receipt reconciliation contention")

    def run(self, h, aid):
        for _ in range(6):
            action = self.store.get("Domain", (hkey(h), f"ACTION#{aid}"))
            if not action or action["status"] in {"CONFIRMED", "CANCELLED", "REJECTED", "BLOCKED"}:
                return
            if action["leaseUntil"] > self.domain.now():
                return
            intent = self.store.get("Delivery", (f"ACTIONRUN#{aid}", "META"))
            if intent and intent["dueAt"] > self.domain.now():
                return
            checks = []
            allowed = True
            if action["status"] == "READY":
                try:
                    ctx = self.domain.context(action["owner"], h)
                    connection = self.get(ctx, "CONNECTION", action["connectionId"], inactive=False)
                    budget = self.budget(ctx)
                    allowed = (
                        ctx.profile["kind"] == "personal"
                        and ctx.member.get("accessEpoch", 1) == action["memberEpoch"]
                        and connection["epoch"] == action["connectionEpoch"]
                        and budget
                        and budget["enabled"]
                        and budget["policyEpoch"] == action["policyEpoch"]
                        and action["quoteExpiresAt"] > self.domain.now()
                    )
                    checks = ctx.guards() + [guard("Domain", connection)]
                    if budget:
                        checks.append(guard("Domain", budget))
                    if action.get("goalId"):
                        goal = self.store.get("Domain", (hkey(h), f"TASK#{action['goalId']}"))
                        cancellation = bool(
                            action.get("goalCancellation") and goal and goal.get("cancelRequested")
                        )
                        goal_allowed = bool(
                            goal
                            and goal.get("operation") == "coordination.goal"
                            and goal["owner"] == action["owner"]
                            and goal["dispatchEpoch"] == action["goalEpoch"]
                            and goal["status"] not in {"PAUSED", "CANCELLED", "FAILED"}
                            and (not goal.get("cancelRequested") or cancellation)
                        )
                        if cancellation and budget and not budget["enabled"]:
                            allowed = (
                                ctx.profile["kind"] == "personal"
                                and ctx.member.get("accessEpoch", 1) == action["memberEpoch"]
                                and connection["epoch"] == action["connectionEpoch"]
                                and budget["policyEpoch"] == action["policyEpoch"]
                                and action["quoteExpiresAt"] > self.domain.now()
                            )
                        allowed = allowed and goal_allowed
                        if goal:
                            checks.append(guard("Domain", goal))
                            if not cancellation:
                                from koyori.goals import validate_goal_sources

                                checks.extend(validate_goal_sources(self.domain, ctx, goal))
                except Problem as exc:
                    if exc.status not in {403, 404, 409}:
                        raise
                    allowed = False
            if not allowed:
                self._block(action, intent, checks)
                return
            new = revised(
                action,
                status="DISPATCHING" if action["status"] == "READY" else "UNKNOWN",
                runEpoch=action["runEpoch"] + 1,
                leaseUntil=self.domain.now() + 30,
            )
            writes = checks + [
                put("Domain", new, action),
                put("Delivery", self.intent(new, intent, self.domain.now() + 30), intent),
            ]
            try:
                self.store.transact(writes)
                break
            except Conflict:
                continue
        else:
            raise Conflict("Action lease contention")
        try:
            receipt = (
                self.provider.execute(new)
                if new["status"] == "DISPATCHING"
                else self.provider.lookup(new)
            )
            if receipt:
                self._finish(new, receipt)
                return
            # Absence is not proof of failure: the original call may still be in flight.
            # Preserve the reservation and poll; never create a new send after revocation.
            raise UnknownOutcome
        except (UnknownOutcome, TimeoutError, OSError):
            current = self.store.get("Domain", (new["PK"], new["SK"]))
            if current["runEpoch"] == new["runEpoch"]:
                intent = self.store.get("Delivery", (f"ACTIONRUN#{aid}", "META"))
                unknown = revised(current, status="UNKNOWN", leaseUntil=0)
                self.store.transact(
                    [
                        put("Domain", unknown, current),
                        put(
                            "Delivery", self.intent(unknown, intent, self.domain.now() + 5), intent
                        ),
                    ]
                )

    def _block(self, action, intent, checks):
        budget = self.store.get("Domain", (action["PK"], f"BUDGET#{action['owner']}"))
        business = self.store.get(
            "Domain", (action["PK"], f"BUSINESS#{action['owner']}#{action['intentionId']}")
        )
        blocked = revised(action, status="BLOCKED", heldMinor=0)
        writes = checks + [
            put("Domain", blocked, action),
            put(
                "Domain",
                revised(budget, heldMinor=budget["heldMinor"] - action["heldMinor"]),
                budget,
            ),
            put(
                "Domain",
                revised(
                    business,
                    status="CONFIRMED"
                    if action["conditions"]["operation"] != "create"
                    else "BLOCKED",
                    actionId=action["previousActionId"],
                ),
                business,
            ),
        ]
        if intent:
            writes.append(put("Delivery", self.domain.done_intent(intent), intent))
        self.store.transact(writes)

    def sweep(self):
        intents = self.pending("ACTIONRUN")
        for intent in intents:
            if intent["dueAt"] <= self.domain.now():
                self.run(intent["h"], intent["actionId"])
        return len(intents)

    def public(self, ctx, category, identifier):
        item = projection(self.get(ctx, category, identifier))
        return {
            k: v for k, v in item.items() if k not in {"providerKey", "runEpoch", "memberEpoch"}
        }
