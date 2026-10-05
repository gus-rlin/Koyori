"""Bounded declarative plans and commands. No model field supplies execution authority."""

from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator

from koyori.contracts import Identifier, Write
from koyori.stage2_contracts import ContextQuery, Line, ProcedureStep, Source


class GoalSubmit(Write):
    text: Annotated[str, Field(min_length=1, max_length=2000)]
    memoryKeys: list[Identifier] = Field(default_factory=list, max_length=8)


class GoalDecision(Write):
    stepId: Identifier
    approvalId: Identifier


class SpecialistResult(Write):
    capability: Literal["memory.context", "calendar.read"]
    evidence: Literal["canonical_memory", "calendar_snapshot"]
    sourceIds: list[Identifier] = Field(default_factory=list, max_length=50)
    sources: list["Reference"] = Field(default_factory=list, max_length=50)
    connectionId: Identifier | None = None
    eventCount: int | None = Field(default=None, ge=0, le=8)
    truncated: bool = False
    observedAt: int = Field(gt=0)
    mode: Literal["real", "simulated"]


class Reference(Write):
    kind: Literal["memory", "connection", "calendar"]
    id: Identifier
    revision: int = Field(ge=1)


class Step(Write):
    stepId: Identifier
    dependsOn: list[Identifier] = Field(default_factory=list, max_length=12)
    dueAt: int | None = Field(default=None, gt=0)


class MemoryStep(Step):
    kind: Literal["read"] = "read"
    capability: Literal["memory.context"] = "memory.context"
    arguments: ContextQuery = Field(default_factory=ContextQuery)
    requiresEvidence: Literal["canonical_memory"] = "canonical_memory"


class CalendarArguments(Write):
    connectionId: Identifier


class CalendarStep(Step):
    kind: Literal["read"] = "read"
    capability: Literal["calendar.read"] = "calendar.read"
    arguments: CalendarArguments
    requiresEvidence: Literal["calendar_snapshot"] = "calendar_snapshot"


class CommerceArguments(Write):
    connectionId: Identifier
    intentKey: Identifier
    lines: list[Line] = Field(min_length=1, max_length=20)
    deliveryAt: int = Field(gt=0)

    @field_validator("lines")
    @classmethod
    def unique_lines(cls, value):
        if len({line.sku for line in value}) != len(value):
            raise ValueError("Duplicate basket lines")
        return value


class CommerceStep(Step):
    kind: Literal["write"] = "write"
    capability: Literal["commerce.groceries", "commerce.meals"]
    arguments: CommerceArguments
    requiresEvidence: Literal["provider_receipt"] = "provider_receipt"


PlanStep = Annotated[MemoryStep | CalendarStep | CommerceStep, Field(discriminator="capability")]


class Plan(Write):
    disposition: Literal["ready", "needs_attention", "unsupported"] = "ready"
    summary: Annotated[str, Field(min_length=1, max_length=500)]
    clarification: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    references: list[Reference] = Field(default_factory=list, max_length=24)
    steps: list[PlanStep] = Field(default_factory=list, max_length=12)
    maxToolCalls: int = Field(default=8, ge=1, le=8)
    maxParallelReads: int = Field(default=2, ge=1, le=2)

    @model_validator(mode="after")
    def graph(self):
        if (self.disposition == "ready") != bool(self.steps):
            raise ValueError("Only a ready plan has steps")
        if self.disposition != "ready" and not self.clarification:
            raise ValueError("An unavailable plan must explain its limit")
        ids = {step.stepId for step in self.steps}
        if len(ids) != len(self.steps):
            raise ValueError("Duplicate step identifiers")
        resolved = set()
        for step in self.steps:
            if len(set(step.dependsOn)) != len(step.dependsOn) or not set(step.dependsOn) <= ids:
                raise ValueError("Invalid dependency")
        while len(resolved) < len(ids):
            ready = {s.stepId for s in self.steps if set(s.dependsOn) <= resolved} - resolved
            if not ready:
                raise ValueError("Cyclic dependency graph")
            resolved |= ready
        intents = [s.arguments.intentKey for s in self.steps if s.kind == "write"]
        if len(intents) != len(set(intents)):
            raise ValueError("One write per commercial intent in a plan")
        if len(self.model_dump_json().encode()) > 24000:
            raise ValueError("Plan exceeds canonical size bound")
        return self


class RoutineWrite(GoalSubmit):
    timeZone: Annotated[str, Field(max_length=64)] = "Europe/Paris"
    localTime: Annotated[str, Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")]
    weekdays: list[int] = Field(default_factory=lambda: list(range(7)), min_length=1, max_length=7)
    startsOn: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
    endsOn: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
    ambiguousTime: Literal["first", "second"] = "first"
    nonexistentTime: Literal["skip", "reject"] = "skip"

    @field_validator("timeZone")
    @classmethod
    def known_zone(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown IANA time zone") from exc
        return value

    @field_validator("weekdays")
    @classmethod
    def distinct_days(cls, value):
        if any(day < 0 or day > 6 for day in value) or len(set(value)) != len(value):
            raise ValueError("Distinct weekday numbers 0..6 required")
        return sorted(value)

    @model_validator(mode="after")
    def bounded_dates(self):
        from datetime import date

        start, end = date.fromisoformat(self.startsOn), date.fromisoformat(self.endsOn)
        if not 0 <= (end - start).days <= 366:
            raise ValueError("Routine must have a bounded horizon up to 366 days")
        return self


class LearningSubmit(Write):
    text: Annotated[str, Field(min_length=1, max_length=2000)]
    kind: Literal["preference", "procedure"]
    key: Identifier
    source: Source
    steps: list[ProcedureStep] = Field(default_factory=list, max_length=16)
    targetMemoryId: Identifier | None = None
    targetRevision: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def declarative(self):
        if (self.kind == "procedure") != bool(self.steps):
            raise ValueError("Only a procedure has declarative steps")
        if bool(self.targetMemoryId) != bool(self.targetRevision):
            raise ValueError("Correction requires the exact memory revision")
        return self


class LearningDecision(Write):
    decision: Literal["accept", "reject"]


class NotificationPolicy(Write):
    timeZone: Annotated[str, Field(max_length=64)] = "Europe/Paris"
    quietStart: Annotated[str, Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")] = "22:00"
    quietEnd: Annotated[str, Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")] = "08:00"
    groupSeconds: int = Field(default=60, ge=0, le=900)

    @field_validator("timeZone")
    @classmethod
    def known_zone(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown IANA time zone") from exc
        return value
