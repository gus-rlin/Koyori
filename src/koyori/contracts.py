"""Versioned, bounded public write contracts; extra fields cannot confer authority."""

from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

Identifier = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]
Label = Annotated[str, Field(min_length=1, max_length=200)]


class Write(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schemaVersion: Literal["1.0"] = "1.0"


class HouseholdCreate(Write):
    name: Label
    timeZone: str = Field(default="Europe/Paris", max_length=64)

    @field_validator("timeZone")
    @classmethod
    def valid_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise ValueError("Unknown IANA time zone") from exc
        return value


class MemberCreate(Write):
    principalId: Identifier
    role: Literal["admin", "member"] = "member"
    kind: Literal["personal", "shared"] = "personal"
    expiresAt: int | None = Field(default=None, gt=0)


class MemberPatch(Write):
    role: Literal["admin", "member"] | None = None
    expiresAt: int | None = Field(default=None, gt=0)


class Command(Write):
    operation: Literal["synthetic.checkpoint"]
    label: Label
    visibility: Literal["private", "household"] = "private"


class TaskPatch(Write):
    label: Label | None = None
    visibility: Literal["private", "household"] | None = None


class DelegationCreate(Write):
    principalId: Identifier
    permissions: list[Literal["read", "control"]] = Field(min_length=1, max_length=2)
    expiresAt: int = Field(gt=0)

    @field_validator("permissions")
    @classmethod
    def unique_permissions(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value) or "read" not in value:
            raise ValueError("Delegations require unique permissions including read")
        return sorted(value)


class PolicyPut(Write):
    enabled: bool
    capability: Literal["synthetic.checkpoint"] = "synthetic.checkpoint"


class StepUpCreate(Write):
    operation: str = Field(
        min_length=6, max_length=256, pattern=r"^(POST|PUT|PATCH|DELETE) /v1/[A-Za-z0-9_/-]+$"
    )
    requestHash: str = Field(pattern=r"^[a-f0-9]{64}$")


class StepUpComplete(Write):
    identityProof: str = Field(min_length=32, max_length=8192)


class Event(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    schemaVersion: Literal["1.0"]
    eventId: Identifier
    type: Literal[
        "koyori.task.changed.v1",
        "koyori.access.changed.v1",
        "koyori.policy.changed.v1",
        "koyori.memory.changed.v1",
        "koyori.action.changed.v1",
        "koyori.connection.changed.v1",
        "koyori.calendar.changed.v1",
        "koyori.routine.changed.v1",
        "koyori.learning.changed.v1",
    ]
    occurredAt: int
    householdId: Identifier
    actorId: Identifier
    aggregateId: Identifier
    aggregateVersion: int = Field(ge=1)
    mode: Literal["sandbox", "simulated", "real"]
    wake: bool = False
    traceparent: str | None = Field(default=None, max_length=55)


def utc(value: int) -> str:
    from datetime import UTC

    return datetime.fromtimestamp(value, UTC).isoformat().replace("+00:00", "Z")
