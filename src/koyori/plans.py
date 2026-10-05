"""Validate a candidate against current sources, accounts and the fixed tool registry."""

from koyori.actions import Actions
from koyori.domain import active, hkey
from koyori.errors import Problem
from koyori.memory import Memory
from koyori.stage3_contracts import Plan
from koyori.store import guard

PROMPT_VERSION = "coordination-1"


def validate_plan(domain, ctx, candidate, *, allowed_connections, allowed_memories):
    plan = Plan.model_validate(candidate)
    checks = []
    for reference in plan.references:
        if reference.kind == "memory":
            if reference.id not in allowed_memories:
                raise Problem(
                    422, "INVALID_PLAN_SOURCE", "Source was not in the authorized context."
                )
            item = Memory(domain).get(ctx, reference.id)
        else:
            if reference.id not in allowed_connections:
                raise Problem(
                    422, "INVALID_PLAN_ACCOUNT", "Account was not in the authorized context."
                )
            item = Actions(domain).get(ctx, "CONNECTION", reference.id, inactive=False)
            if reference.kind == "calendar":
                if item["provider"] != "google-calendar":
                    raise Problem(
                        422, "INVALID_PLAN_SOURCE", "Source is not an authorized calendar."
                    )
                checks.append(guard("Domain", item))
                item = domain.store.get("Domain", (hkey(ctx.h), f"CALVERSION#{reference.id}"))
                if not item:
                    raise Problem(
                        409, "CALENDAR_NOT_SYNCHRONIZED", "Synchronize the calendar first."
                    )
        if item["rev"] != reference.revision:
            raise Problem(409, "PLAN_CONTEXT_CHANGED", "A planning source has changed.")
        checks.append(guard("Domain", item))
    for step in plan.steps:
        if step.dueAt is not None and step.dueAt > domain.now() + 366 * 86400:
            raise Problem(422, "INVALID_PLAN_TIME", "Step exceeds the scheduling horizon.")
        if step.capability == "memory.context":
            continue
        cid = step.arguments.connectionId
        if cid not in allowed_connections:
            raise Problem(422, "INVALID_PLAN_ACCOUNT", "Account was not in the authorized context.")
        connection = Actions(domain).get(ctx, "CONNECTION", cid, inactive=False)
        if (
            not active(connection, domain.now())
            or step.capability not in connection["capabilities"]
        ):
            raise Problem(422, "INVALID_PLAN_CAPABILITY", "Account lacks this capability.")
        expected_provider = "google-calendar" if step.kind == "read" else "commerce-simulator"
        if connection["provider"] != expected_provider:
            raise Problem(
                422, "INVALID_PLAN_PROVIDER", "Provider does not match the registered tool."
            )
        checks.append(guard("Domain", connection))
        if step.kind == "write":
            if not domain.now() < step.arguments.deliveryAt <= domain.now() + 366 * 86400:
                raise Problem(
                    422, "INVALID_PLAN_TIME", "Delivery must be within the future horizon."
                )
            if step.dueAt is not None and step.dueAt >= step.arguments.deliveryAt:
                raise Problem(422, "INVALID_PLAN_TIME", "Execution must precede delivery.")
            meals = {"vegetarian-meal", "chicken-meal"}
            if any(
                (line.sku in meals) != (step.capability == "commerce.meals")
                for line in step.arguments.lines
            ):
                raise Problem(
                    422, "INVALID_PLAN_LINES", "Basket does not match the registered tool."
                )
    return plan.model_dump(), checks
