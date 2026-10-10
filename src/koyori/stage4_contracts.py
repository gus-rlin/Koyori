"""Bounded channel contracts. Identity and approval never appear in tool arguments."""

from typing import Literal

from pydantic import Field

from koyori.contracts import Write as Strict
from koyori.stage2_contracts import CalendarEventDraft


class SessionCreate(Strict):
    mode: Literal["shared", "personal"] = "shared"
    microphoneConsent: Literal[True]
    conversationId: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    locale: Literal["fr-FR", "en-US"] = "fr-FR"


class Bootstrap(Strict):
    type: Literal["session.bootstrap"]
    protocolVersion: Literal["1.0"]
    runtimeSessionId: str = Field(pattern=r"^[a-f0-9-]{36}$")
    ticket: str = Field(min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]+$")
    inputFormat: Literal["pcm16-16000-mono"] = "pcm16-16000-mono"


class VoiceControl(Strict):
    type: Literal[
        "turn.final",
        "playback.interrupt",
        "session.heartbeat",
        "session.close",
        "session.renew",
        "playback.backpressure",
    ]
    turnId: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    text: str | None = Field(default=None, min_length=1, max_length=4000)
    bufferedMs: int | None = Field(default=None, ge=0, le=10000)


class TaskStatus(Strict):
    taskId: str = Field(pattern=r"^[a-f0-9]{32}$")


class Recall(Strict):
    day: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    timeZone: str = Field(default="Europe/Paris", max_length=100)
    cursor: str | None = Field(default=None, max_length=2048)


class GoalControl(Strict):
    taskId: str = Field(pattern=r"^[a-f0-9]{32}$")
    revision: int = Field(ge=1)
    idempotencyKey: str = Field(pattern=r"^[a-f0-9]{32}$")


class GoalInput(Strict):
    text: str = Field(min_length=1, max_length=2000)
    idempotencyKey: str = Field(pattern=r"^[a-f0-9]{32}$")


class EventProposal(CalendarEventDraft):
    idempotencyKey: str = Field(pattern=r"^[a-f0-9]{32}$")


class MemoryErase(Strict):
    confirmation: Literal["erase-my-memories"]
