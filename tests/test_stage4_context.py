"""Channel agenda goes through the existing provider reader and its authority checks."""

import pytest
from test_stage2_calendar import connect

from koyori.channel_tools import ChannelTools
from koyori.errors import Problem
from koyori.goals import Goals
from koyori.sessions import Sessions
from koyori.store import put, revised

pytest_plugins = ["test_stage2_calendar"]


def test_daily_context_reuses_calendar_sources_and_hides_personal_shared(calendar):
    h, service = calendar
    connected, _ = connect(h, service)
    ctx = h.domain.context("alex", h.h)
    service.sync(ctx, connected["id"])
    tools = ChannelTools(h.domain, Goals(h.domain, calendar=service))
    sessions = Sessions(h.domain)
    secret = sessions.grant(ctx)
    value = tools.call(secret, "get_daily_context", {})
    assert value["calendars"][0]["items"][0]["summary"] == "Dinner"
    assert value["calendars"][0]["evidence"] == "calendar_snapshot"
    shared = sessions.grant(h.domain.context("speaker", h.h), mode="shared")
    assert tools.call(shared, "get_daily_context", {})["calendars"] == []
    connection = service.get(ctx, connected["id"])
    h.domain.store.transact([put("Domain", revised(connection, active=False), connection)])
    with pytest.raises(Problem):
        tools.result_checks(ctx, value)


def test_calendar_provider_revocation_never_returns_stale_channel_agenda(calendar):
    h, service = calendar
    connected, _ = connect(h, service)
    ctx = h.domain.context("alex", h.h)
    service.sync(ctx, connected["id"])
    tools = ChannelTools(h.domain, Goals(h.domain, calendar=service))
    secret = Sessions(h.domain).grant(ctx)
    service.google.allowed = False
    with pytest.raises(Problem, match="CALENDAR_ACCESS_REVOKED"):
        tools.call(secret, "get_daily_context", {})
