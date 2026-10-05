"""Authorization for minimal activity envelopes; reload the current object on every read."""

from koyori.actions import Actions
from koyori.memory import Memory
from koyori.store import guard


def event_access(domain, ctx, kind, identifier):
    if kind == "koyori.memory.changed.v1":
        item = Memory(domain).get(ctx, identifier, tombstone=True)
    elif kind == "koyori.action.changed.v1":
        item = Actions(domain).get(ctx, "ACTION", identifier)
    elif kind in {"koyori.connection.changed.v1", "koyori.calendar.changed.v1"}:
        item = Actions(domain).get(ctx, "CONNECTION", identifier)
    else:
        domain.admin(ctx)
        return []
    return [guard("Domain", item)]
