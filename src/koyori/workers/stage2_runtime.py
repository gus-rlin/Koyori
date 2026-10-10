"""Bounded stage-two roles, separate from synthetic workflow dispatch."""

from koyori.actions import Actions
from koyori.agenda import Agenda
from koyori.calendar import Calendar
from koyori.semantic import Semantic


def tick(domain, role):
    if role == "projection":
        from koyori.lexical import Lexical

        lexical = Lexical(domain).sweep()
        return lexical + Semantic(domain).sweep()
    actions = Actions(domain).sweep()
    calendars = Calendar(domain).sweep()
    return actions + calendars + Agenda(domain).sweep()


def connectors(event, context):
    from koyori.workers.runtime import engine

    if event.get("channelRead"):
        from koyori.channel_tools import channel_calendar_read

        return channel_calendar_read(engine().domain, event)
    if event.get("goalRead"):
        from koyori.workers.stage3_runtime import calendar_read

        return calendar_read(engine().domain, event)
    return {"attempted": tick(engine().domain, "connector")}


def projections(event, context):
    from koyori.workers.runtime import engine

    return {"attempted": tick(engine().domain, "projection")}
