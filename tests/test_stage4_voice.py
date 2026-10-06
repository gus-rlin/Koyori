"""Wire framing, playback interruption, disconnect and final transcript boundaries."""

import struct
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_stage4_sessions import admission

from koyori.errors import Problem
from koyori.voice import VoiceSession, create_voice_app


def bootstrap(grant):
    return {
        "type": "session.bootstrap",
        "protocolVersion": "1.0",
        "ticket": grant["ticket"],
        "runtimeSessionId": grant["runtimeSessionId"],
    }


def test_socket_finalize_interrupt_disconnect_and_rest_state(harness):
    h = harness
    s, grant = admission(h)
    client = TestClient(create_voice_app(domain=h.domain, tools=h.client.app.state.mcp.tools))
    with client.websocket_connect("/ws") as ws:
        ws.send_json(bootstrap(grant))
        assert ws.receive_json()["type"] == "session.ready"
        ws.send_json(
            {"type": "turn.final", "turnId": uuid4().hex, "text": "Prépare le dîner pour deux"}
        )
        final = ws.receive_json()
        assert final["type"] == "turn.finalized", final
        ws.send_json({"type": "playback.interrupt"})
        for _ in range(4):
            message = ws.receive_json()
            if message["type"] == "playback.stopped":
                assert message["generation"] >= 1
                break
        else:
            pytest.fail("Interruption not acknowledged")
        ws.send_json({"type": "session.close"})
    assert h.task(final["taskId"])["status"] == "READY"
    with pytest.raises(Problem):
        s.check(grant["runtimeSessionId"])


def test_frame_bounds_stale_generation_duplicate_and_upload_limit(harness):
    h = harness
    s, grant = admission(h)
    s.consume(grant["ticket"], grant["runtimeSessionId"])
    bridge = VoiceSession(h.domain, grant["runtimeSessionId"])
    assert bridge.frame(struct.pack("<II", 0, 0) + b"\0\0") == b"\0\0"
    with pytest.raises(Problem, match="AUDIO_SEQUENCE"):
        bridge.frame(struct.pack("<II", 0, 0) + b"\0\0")
    bridge.interrupt()
    with pytest.raises(Problem, match="AUDIO_SEQUENCE"):
        bridge.frame(struct.pack("<II", 1, 0) + b"\0\0")
    with pytest.raises(Problem, match="INVALID_AUDIO_FRAME"):
        bridge.frame(b"\0" * 9)
    bridge.input_bytes = 1000000
    with pytest.raises(Problem, match="AUDIO_RATE_LIMIT"):
        bridge.frame(struct.pack("<II", 1, 1) + b"\0\0")


def test_bootstrap_denies_expired_ticket_and_unknown_origin(harness):
    h = harness
    _, grant = admission(h)
    h.clock.advance(30)
    client = TestClient(create_voice_app(domain=h.domain))
    with client.websocket_connect("/ws") as ws:
        ws.send_json(bootstrap(grant))
        assert ws.receive_json()["type"] == "session.error"
    from starlette.websockets import WebSocketDisconnect

    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/ws", headers={"Origin": "https://evil.invalid"}),
    ):
        pass


def test_close_voice_never_cancels_goal(harness):
    h = harness
    s, grant = admission(h)
    s.consume(grant["ticket"], grant["runtimeSessionId"])
    bridge = VoiceSession(h.domain, grant["runtimeSessionId"], h.client.app.state.mcp.tools)
    saved = bridge.finalize(uuid4().hex, "Prépare le dîner pour deux", submit=True)
    bridge.interrupt()
    s.close(grant["runtimeSessionId"])
    assert h.task(saved["taskId"])["executionAuthorized"] is True


def test_playback_rechecks_shared_sources_after_correction(harness):
    from koyori.memory import Memory
    from koyori.stage2_contracts import MemoryWrite

    h = harness
    ctx = h.domain.context("sam", h.h)
    memory = Memory(h.domain)
    saved, writes, _ = memory.create(
        ctx,
        MemoryWrite(kind="exchange", text="Ancien contenu", visibility="household").model_dump(),
    )
    h.domain.store.transact(ctx.guards() + writes)
    s, grant = admission(h)
    s.consume(grant["ticket"], grant["runtimeSessionId"])
    bridge = VoiceSession(h.domain, grant["runtimeSessionId"])
    secret = s.grant(h.domain.context("alex", h.h))
    value = bridge.tools.call(secret, "get_daily_context", {})
    bridge.validate_result(value)
    current = memory.get(ctx, saved["id"])
    _, changes, _ = memory.change(ctx, saved["id"], {"text": "Corrigé"}, current["rev"])
    h.domain.store.transact(ctx.guards() + changes)
    with pytest.raises(Problem, match="CONTEXT_CHANGED"):
        bridge.validate_result(value)


def test_playback_refuses_shared_memory_as_soon_as_owner_erasure_is_accepted(harness):
    from koyori.memory import Memory
    from koyori.privacy import Privacy
    from koyori.stage2_contracts import MemoryWrite

    h = harness
    owner = h.domain.context("sam", h.h)
    _, changes, _ = Memory(h.domain).create(
        owner,
        MemoryWrite(
            kind="exchange", text="Stop this playback", visibility="household"
        ).model_dump(),
    )
    h.domain.store.transact(owner.guards() + changes)
    sessions, grant = admission(h)
    sessions.consume(grant["ticket"], grant["runtimeSessionId"])
    bridge = VoiceSession(h.domain, grant["runtimeSessionId"])
    secret = sessions.grant(h.domain.context("alex", h.h))
    value = bridge.tools.call(secret, "get_daily_context", {})
    bridge.validate_result(value)
    _, erasing, _ = Privacy(h.domain).start(owner)
    h.domain.store.transact(owner.guards() + erasing)
    with pytest.raises(Problem):
        bridge.validate_result(value)
