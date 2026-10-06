"""Coordinator, wake repair and grouped notifications run separately from provider recovery."""

from koyori.domain import hkey
from koyori.goals import Goals
from koyori.notifications import Notifications
from koyori.scheduling import Wakes


def calendar_read(domain, event):
    from koyori.calendar import Calendar
    from koyori.errors import Problem
    from koyori.goals import calendar_snapshot

    task = domain.store.get("Domain", (hkey(event["householdId"]), f"TASK#{event['taskId']}"))
    if (
        not task
        or task.get("operation") != "coordination.goal"
        or task["runEpoch"] != event["runEpoch"]
        or task["status"] != "RUNNING"
        or task["leaseUntil"] <= domain.now()
    ):
        raise Problem(409, "RUN_SUPERSEDED", "Calendar request has no current goal run.")
    ctx = domain.context(task["owner"], event["householdId"])
    if ctx.member.get("accessEpoch", 1) != task["grantEpoch"]:
        raise Problem(403, "ACCESS_REVOKED", "Goal authority changed.")
    return calendar_snapshot(Calendar(domain), ctx, event["connectionId"])


def tick(domain, role):
    if role == "coordinator":
        if domain.settings.coordinator_machine_arn:
            from koyori.workflows import Workflows

            return Workflows(domain).sweep()
        return Goals(domain).sweep()
    if role == "scheduler":
        return Wakes(domain).sweep()
    return Notifications(domain).sweep()


def coordinate(event, context):
    from koyori.workers.runtime import engine

    domain = engine().domain
    task = domain.store.get("Domain", (hkey(event["householdId"]), f"TASK#{event['taskId']}"))
    if not task or task["runEpoch"] != event["runEpoch"] or task["leaseUntil"] <= domain.now():
        return {"status": "SUPERSEDED"}
    Goals(domain).run(event["householdId"], event["taskId"], run=task)
    return {"status": "RECONCILED"}


def dispatch(event, context):
    from koyori.workers.runtime import engine

    return {"attempted": tick(engine().domain, "coordinator")}


def schedules(event, context):
    from koyori.workers.runtime import engine

    domain = engine().domain
    if "wakeId" in event:
        Wakes(domain).deliver(event["wakeId"])
    return {"attempted": tick(domain, "scheduler")}


def notify(event, context):
    from koyori.workers.runtime import engine

    return {"attempted": tick(engine().domain, "notifications")}
