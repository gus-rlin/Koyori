"""Bounded stage-two roles, separate from synthetic workflow dispatch."""

from koyori.actions import Actions
from koyori.calendar import Calendar
from koyori.semantic import Semantic


def tick(domain, role):
    if role == "projection":
        return Semantic(domain).sweep()
    actions = Actions(domain).sweep()
    calendars = Calendar(domain).sweep()
    return actions + calendars


def connectors(event, context):
    from koyori.workers.runtime import engine

    return {"attempted": tick(engine().domain, "connector")}


def projections(event, context):
    from koyori.workers.runtime import engine

    return {"attempted": tick(engine().domain, "projection")}
