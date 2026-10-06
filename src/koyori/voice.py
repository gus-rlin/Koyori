"""Bounded WebSocket bridge. Playback generations never change commercial state."""

import asyncio
import struct
import time
from contextlib import suppress

import anyio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from koyori.channel_tools import ChannelTools
from koyori.domain import row
from koyori.errors import Conflict, Problem
from koyori.memory import Memory
from koyori.security import digest
from koyori.sessions import PERSONAL_TOOLS, READ_TOOLS, Sessions
from koyori.speech import NovaSpeech, Polly, narration
from koyori.stage2_contracts import MemoryWrite
from koyori.stage4_contracts import Bootstrap, VoiceControl
from koyori.store import guard, put


class VoiceSession:
    def __init__(self, domain, sid, tools=None):
        self.domain, self.sid = domain, sid
        self.sessions, self.tools = Sessions(domain), tools or ChannelTools(domain)
        self.generation, self.input_sequence, self.output_sequence = 0, 0, 0
        self.input_bytes, self.tool_calls, self.turns = 0, 0, 0
        self.started = time.monotonic()
        self.stream_started = self.started

    def check(self, activity=False):
        return self.sessions.check(self.sid, activity=activity)

    def frame(self, raw):
        if len(raw) < 10 or len(raw) > 6408 or (len(raw) - 8) % 2:
            raise Problem(400, "INVALID_AUDIO_FRAME", "Use bounded mono PCM16 frames.")
        sequence, generation = struct.unpack("<II", raw[:8])
        if sequence != self.input_sequence or generation != self.generation:
            raise Problem(409, "AUDIO_SEQUENCE", "Audio is stale or out of sequence.")
        self.check(activity=True)
        self.input_sequence += 1
        self.input_bytes += len(raw) - 8
        # Protect against accelerated uploads even when application clocks are mocked.
        if self.input_bytes > (time.monotonic() - self.started + 2) * 32000:
            raise Problem(429, "AUDIO_RATE_LIMIT", "Audio upload exceeds realtime capacity.")
        return raw[8:]

    def interrupt(self):
        self.check()
        self.generation += 1
        return {"type": "playback.stopped", "generation": self.generation}

    def validate_result(self, value):
        ctx, session = self.check()
        checks = self.tools.result_checks(ctx, value)
        if value.get("id") and "status" in value:
            current, authority = self.domain.task_access(ctx, value["id"])
            if current["rev"] != value.get("rev"):
                raise Problem(503, "CONTEXT_CHANGED", "Task changed before playback.", True)
            checks.extend(authority)
            from koyori.actions import Actions

            for action in value.get("actions", []):
                current = Actions(self.domain).get(ctx, "ACTION", action["id"])
                if current["rev"] != action["rev"]:
                    raise Problem(503, "CONTEXT_CHANGED", "Action changed before playback.", True)
                checks.append(guard("Domain", current))
        privacy_epoch, privacy_check = self.sessions._privacy(ctx)
        if session.get("privacyEpoch", 0) != privacy_epoch:
            raise Problem(403, "FORBIDDEN", "Privacy authority changed.")
        self.domain.store.transact(
            ctx.guards() + checks + [privacy_check, guard("Sessions", session)]
        )

    def finalize(self, turn, text, *, submit=False):
        if not text.strip() or len(text) > 2000 or self.turns >= 64:
            raise Problem(422, "INVALID_TURN", "Final transcript exceeds bounds.")
        self.check(activity=True)
        key = (f"VOICETURN#{self.sid}", f"TURN#{turn}")
        hashed = digest({"text": text})
        for _ in range(6):
            ctx, session = self.check()
            cached = self.domain.store.get("Sessions", key)
            if cached:
                if cached["requestHash"] != hashed:
                    raise Problem(409, "TURN_CONFLICT", "Final turn has different content.")
                return {"memoryId": cached["memoryId"], "taskId": cached.get("taskId")}
            visibility = "private" if session["mode"] == "personal" else "household"
            body = MemoryWrite(kind="exchange", text=text, visibility=visibility).model_dump()
            saved, writes, _ = Memory(self.domain).create(ctx, body)
            task_id = None
            if submit:
                if session["mode"] != "personal":
                    raise Problem(
                        403,
                        "PERSONAL_MODE_REQUIRED",
                        "A shared voice session can read shared context.",
                    )
                from koyori.stage3_contracts import GoalSubmit

                task, changes, _ = self.tools.goals.create(ctx, GoalSubmit(text=text).model_dump())
                task_id = task["id"]
                writes.extend(changes)
            receipt = row(*key, requestHash=hashed, memoryId=saved["id"], taskId=task_id)
            try:
                self.domain.store.transact(
                    ctx.guards()
                    + [guard("Sessions", session)]
                    + writes
                    + [put("Sessions", receipt)]
                )
                self.turns += 1
                return {"memoryId": saved["id"], "taskId": task_id}
            except Conflict:
                continue
        raise Problem(503, "CONTENTION", "Retry the same final turn.", True)

    def tool(self, identifier, name, arguments):
        ctx, session = self.check(activity=True)
        self.tool_calls += 1
        if self.tool_calls > 32:
            raise Problem(429, "VOICE_TOOL_LIMIT", "Interactive tool ceiling reached.")
        allowed = PERSONAL_TOOLS if session["mode"] == "personal" else READ_TOOLS
        if name not in allowed:
            raise Problem(403, "TOOL_FORBIDDEN", "This tool is not admitted.")
        if not isinstance(arguments, dict):
            raise Problem(422, "INVALID_TOOL_ARGUMENTS", "Tool arguments must be an object.")
        arguments = {**arguments}
        if name.endswith("_goal"):
            # Model-selected keys cannot create two operations for one tool occurrence.
            arguments["idempotencyKey"] = digest({"sid": self.sid, "tool": identifier})[:32]
        secret = self.sessions.grant(ctx, mode=session["mode"], session_id=self.sid)
        return self.tools.call(secret, name, arguments)


def create_voice_app(*, domain=None, speech_factory=None, tools=None, polly=None):
    if domain is None:
        from koyori.config import Settings
        from koyori.domain import Domain
        from koyori.security import Cursors
        from koyori.store import DynamoStore

        settings = Settings.from_env()
        domain = Domain(DynamoStore(settings), settings, Cursors(settings.cursor_secret()))
    app = FastAPI(docs_url=None, redoc_url=None)
    app.state.domain = domain
    app.state.active_connections = 0
    synthesis = polly or Polly(domain.settings)

    @app.get("/ping")
    def ping():
        return {"status": "HealthyBusy" if app.state.active_connections else "Healthy"}

    @app.websocket("/ws")
    async def websocket(ws: WebSocket):
        origin = ws.headers.get("origin")
        if origin and origin not in domain.settings.allowed_origins:
            await ws.close(code=1008)
            return
        await ws.accept()
        sid, speech, output_task, bridge = None, None, None, None
        send_lock = asyncio.Lock()
        playback_task = None

        async def json_message(value):
            async with send_lock:
                await ws.send_json(value)

        async def play(value, locale):
            generation = bridge.generation
            await anyio.to_thread.run_sync(bridge.validate_result, value)
            announcement = narration(value, locale)
            await json_message(
                {
                    "type": "speech.result",
                    "generation": generation,
                    **announcement,
                    "simulation": domain.settings.speech_mode == "simulated",
                }
            )
            audio = await anyio.to_thread.run_sync(synthesis.synthesize, announcement, locale)
            for start in range(0, len(audio), 3200):
                await anyio.to_thread.run_sync(bridge.validate_result, value)
                if generation != bridge.generation:
                    return
                async with send_lock:
                    await ws.send_bytes(
                        struct.pack("<II", bridge.output_sequence, generation)
                        + audio[start : start + 3200]
                    )
                bridge.output_sequence += 1
                # Pacing makes interruption and bounded client playback observable.
                await asyncio.sleep(0.1)
            await json_message({"type": "playback.complete", "generation": generation})

        async def announce(value, locale):
            nonlocal playback_task
            if playback_task and not playback_task.done():
                playback_task.cancel()
                with suppress(asyncio.CancelledError):
                    await playback_task
                bridge.interrupt()
            playback_task = asyncio.create_task(play(value, locale))

        async def read_provider(session):
            async for event in speech.events():
                await anyio.to_thread.run_sync(bridge.check)
                if event["type"] == "transcript":
                    turn = digest(
                        {"sid": sid, "stream": bridge.stream_started, "content": event["id"]}
                    )[:32]
                    saved = await anyio.to_thread.run_sync(bridge.finalize, turn, event["text"])
                    await json_message({"type": "turn.finalized", "turnId": turn, **saved})
                elif event["type"] == "tool":
                    try:
                        value = await anyio.to_thread.run_sync(
                            bridge.tool, event["id"], event["name"], event["arguments"]
                        )
                    except Problem as exc:
                        value = {"code": exc.code, "retryable": exc.retryable}
                    await speech.tool_result(event["id"], value)
                    await json_message(
                        {"type": "tool.result", "name": event["name"], "result": value}
                    )
                    await announce(value, session["locale"])
                # Provider usage is recorded as aggregate numbers, never raw content.
                elif event["type"] == "usage":
                    await json_message(
                        {"type": "usage", "measuredBy": "provider", "units": event["units"]}
                    )

        async def open_speech(session):
            nonlocal speech, output_task
            speech = (speech_factory or NovaSpeech)(domain.settings)
            ctx, _ = await anyio.to_thread.run_sync(bridge.check)
            secret = await anyio.to_thread.run_sync(
                lambda: bridge.sessions.grant(ctx, mode=session["mode"], session_id=sid)
            )
            context = await anyio.to_thread.run_sync(
                bridge.tools.call, secret, "get_daily_context", {}
            )
            allowed = PERSONAL_TOOLS if session["mode"] == "personal" else READ_TOOLS
            await asyncio.wait_for(speech.open(context, allowed), 10)
            bridge.stream_started = time.monotonic()
            output_task = asyncio.create_task(read_provider(session))

        try:
            raw = await asyncio.wait_for(ws.receive_text(), 5)
            if len(raw.encode()) > 8192:
                raise Problem(413, "BOOTSTRAP_TOO_LARGE", "Bootstrap exceeds bounds.")
            bootstrap = Bootstrap.model_validate_json(raw)
            transport_sid = ws.headers.get(
                "x-amzn-bedrock-agentcore-runtime-session-id"
            ) or ws.query_params.get("X-Amzn-Bedrock-AgentCore-Runtime-Session-Id")
            if domain.settings.env != "local" and transport_sid != bootstrap.runtimeSessionId:
                raise Problem(403, "SESSION_BINDING", "Runtime transport session differs.")
            session = await anyio.to_thread.run_sync(
                Sessions(domain).consume, bootstrap.ticket, bootstrap.runtimeSessionId
            )
            sid, bridge = (
                session["runtimeSessionId"],
                VoiceSession(domain, session["runtimeSessionId"], tools),
            )
            app.state.active_connections += 1
            if domain.settings.speech_mode == "aws":
                await open_speech(session)
            await json_message(
                {
                    "type": "session.ready",
                    "protocolVersion": "1.0",
                    "runtimeSessionId": sid,
                    "conversationId": session["conversationId"],
                    "generation": 0,
                    "inputFormat": "pcm16-16000-mono",
                    "outputFormat": "pcm16-16000-mono",
                    "simulation": domain.settings.speech_mode == "simulated",
                    "transactionSpeech": "source-templates",
                }
            )
            while True:
                await anyio.to_thread.run_sync(bridge.check)
                if output_task and output_task.done():
                    output_task.result()
                    raise Problem(502, "SPEECH_ENDED", "Speech stream ended; reconnect.")
                if playback_task and playback_task.done():
                    playback_task.result()
                    playback_task = None
                # Renewal before the provider's eight-minute stream limit.
                if speech and time.monotonic() - bridge.stream_started >= 420:
                    output_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await output_task
                    await asyncio.wait_for(speech.close(), 5)
                    await open_speech(session)
                    await json_message({"type": "stream.renewed", "generation": bridge.generation})
                try:
                    message = await asyncio.wait_for(ws.receive(), 1)
                except TimeoutError:
                    continue
                if message["type"] == "websocket.disconnect":
                    break
                if message.get("bytes") is not None:
                    pcm = await anyio.to_thread.run_sync(bridge.frame, message["bytes"])
                    if speech:
                        await asyncio.wait_for(speech.audio(pcm), 2)
                    continue
                raw = message.get("text", "")
                if len(raw.encode()) > 8192:
                    raise Problem(413, "CONTROL_TOO_LARGE", "Control exceeds bounds.")
                control = VoiceControl.model_validate_json(raw)
                if control.type == "session.close":
                    break
                if control.type == "session.heartbeat":
                    await json_message({"type": "session.alive"})
                elif control.type == "playback.backpressure":
                    if control.bufferedMs is None or control.bufferedMs > 2000:
                        await json_message(bridge.interrupt())
                elif control.type == "playback.interrupt":
                    await json_message(bridge.interrupt())
                elif control.type == "session.renew":
                    if speech:
                        bridge.stream_started = 0
                    else:
                        await json_message({"type": "stream.renewed", "simulation": True})
                elif control.type == "turn.final":
                    if (
                        domain.settings.speech_mode != "simulated"
                        or not control.turnId
                        or not control.text
                    ):
                        raise Problem(
                            422,
                            "FINAL_TRANSCRIPT_FORBIDDEN",
                            "Final speech comes from the configured provider.",
                        )
                    # Synthetic text input explicitly exercises finalized transcript admission.
                    saved = await anyio.to_thread.run_sync(
                        lambda control=control: bridge.finalize(
                            control.turnId, control.text, submit=session["mode"] == "personal"
                        )
                    )
                    await json_message(
                        {"type": "turn.finalized", "turnId": control.turnId, **saved}
                    )
                    value = (
                        bridge.tools.goals.public(
                            domain.context(session["actor"], session["h"]), saved["taskId"]
                        )
                        if saved["taskId"]
                        else {}
                    )
                    await announce(value, session["locale"])
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except (Problem, ValidationError, ValueError, TimeoutError) as exc:
            with suppress(RuntimeError, WebSocketDisconnect):
                await json_message(
                    {
                        "type": "session.error",
                        "code": exc.code if isinstance(exc, Problem) else "INVALID_PROTOCOL",
                    }
                )
        except Exception:
            with suppress(RuntimeError, WebSocketDisconnect):
                await json_message({"type": "session.error", "code": "DEPENDENCY_UNAVAILABLE"})
        finally:
            for pending in (playback_task, output_task):
                if pending:
                    pending.cancel()
                    with suppress(asyncio.CancelledError, Exception):
                        await pending
            if speech:
                with suppress(Exception):
                    await asyncio.wait_for(speech.close(), 5)
            if sid:
                app.state.active_connections -= 1
                with suppress(Exception):
                    await anyio.to_thread.run_sync(Sessions(domain).close, sid)
            with suppress(RuntimeError, WebSocketDisconnect):
                await ws.close(code=1000)

    return app
