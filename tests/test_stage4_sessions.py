"""Admission races, opaque authority, channel privacy and connection-independent tasks."""

from dataclasses import replace
from uuid import uuid4

import pytest

from koyori.channel_tools import ChannelTools
from koyori.domain import hkey
from koyori.errors import Problem
from koyori.sessions import Sessions
from koyori.stage4_contracts import SessionCreate
from koyori.store import put, revised
from koyori.voice import VoiceSession


def admission(h, mode="personal", **values):
    h.domain.settings = replace(h.domain.settings, speech_mode="simulated")
    service = Sessions(h.domain)
    ctx = h.domain.context("alex", h.h)
    return service, service.issue(
        ctx, SessionCreate(mode=mode, microphoneConsent=True, **values).model_dump()
    )


def test_ticket_is_single_use_and_does_not_store_bearer(harness):
    h = harness
    s, grant = admission(h)
    stored = h.domain.store.get("Sessions", s._key("TICKET", grant["ticket"]))
    assert grant["ticket"] not in str(stored)
    with pytest.raises(Problem):
        s.consume(grant["ticket"], str(uuid4()))
    s.consume(grant["ticket"], grant["runtimeSessionId"])
    with pytest.raises(Problem):
        s.consume(grant["ticket"], grant["runtimeSessionId"])


def test_expired_admission_and_revocation_refuse_before_context(harness):
    h = harness
    s, grant = admission(h)
    h.clock.advance(31)
    with pytest.raises(Problem):
        s.consume(grant["ticket"], grant["runtimeSessionId"])
    s, grant = admission(h)
    member = h.domain.store.get("Domain", (hkey(h.h), "MEMBER#alex"))
    h.domain.store.transact([put("Domain", revised(member, accessEpoch=2), member)])
    with pytest.raises(Problem):
        s.consume(grant["ticket"], grant["runtimeSessionId"])


def test_voice_quota_idle_and_heartbeat_not_activity(harness):
    h = harness
    s, a = admission(h)
    _, b = admission(h)
    with pytest.raises(Problem, match="VOICE_CAPACITY"):
        admission(h)
    s.close(b["runtimeSessionId"])
    s.consume(a["ticket"], a["runtimeSessionId"])
    h.clock.advance(60)
    with pytest.raises(Problem):
        s.check(a["runtimeSessionId"])
    s.close(a["runtimeSessionId"])


def test_shared_grant_cannot_submit_or_read_private_task(harness):
    h = harness
    private = h.command()
    service, ticket = admission(h, "shared")
    session = service.consume(ticket["ticket"], ticket["runtimeSessionId"])
    ctx = h.domain.context("alex", h.h)
    secret = service.grant(ctx, mode="shared", session_id=session["runtimeSessionId"])
    tools = ChannelTools(h.domain)
    with pytest.raises(Problem):
        tools.call(secret, "submit_goal", {"text": "Buy dinner", "idempotencyKey": uuid4().hex})
    with pytest.raises(Problem):
        tools.call(secret, "get_task_status", {"taskId": private})
    assert tools.call(secret, "get_daily_context", {})["items"] == []


def test_finalized_turn_atomic_and_reconnect_retains_same_task(harness):
    h = harness
    s, ticket = admission(h)
    s.consume(ticket["ticket"], ticket["runtimeSessionId"])
    bridge = VoiceSession(h.domain, ticket["runtimeSessionId"], h.client.app.state.mcp.tools)
    turn = uuid4().hex
    saved = bridge.finalize(turn, "Prépare le dîner pour deux", submit=True)
    assert bridge.finalize(turn, "Prépare le dîner pour deux", submit=True) == saved
    with pytest.raises(Problem, match="TURN_CONFLICT"):
        bridge.finalize(turn, "Other text", submit=True)
    s.close(ticket["runtimeSessionId"])
    _, reconnect = admission(h, conversationId=ticket["conversationId"])
    assert reconnect["conversationId"] == ticket["conversationId"]
    assert reconnect["runtimeSessionId"] != ticket["runtimeSessionId"]
    assert h.task(saved["taskId"])["status"] == "READY"
    assert h.domain.context("alex", h.h).household["activeTasks"] == 1


def test_grant_bound_to_closed_voice_and_expiration(harness):
    h = harness
    s, a = admission(h)
    s.consume(a["ticket"], a["runtimeSessionId"])
    secret = s.grant(h.domain.context("alex", h.h), session_id=a["runtimeSessionId"])
    s.close(a["runtimeSessionId"])
    with pytest.raises(Problem):
        s.resolve(secret, "get_daily_context")
    secret = s.grant(h.domain.context("alex", h.h))
    h.clock.advance(30)
    with pytest.raises(Problem):
        s.resolve(secret)


def test_resume_other_actor_or_mode_is_forbidden(harness):
    h = harness
    service, ticket = admission(h)
    body = SessionCreate(
        mode="personal", microphoneConsent=True, conversationId=ticket["conversationId"]
    ).model_dump()
    with pytest.raises(Problem):
        service.issue(h.domain.context("sam", h.h), body)
    with pytest.raises(Problem):
        admission(h, "shared", conversationId=ticket["conversationId"])
