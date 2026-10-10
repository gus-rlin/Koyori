"""Explicit stage-two commands. Client input never selects provider mode or authority."""

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from koyori.contracts import Identifier, Write

Text = Annotated[str, Field(min_length=1, max_length=6000)]


class Source(Write):
    kind: Literal["declaration", "memory", "task", "action"] = "declaration"
    id: Identifier | None = None

    @model_validator(mode="after")
    def reference(self):
        if (self.kind == "declaration") != (self.id is None):
            raise ValueError("A reference is required for linked sources only")
        return self


class ProcedureStep(Write):
    capability: Literal["calendar.read", "commerce.groceries", "commerce.meals"]
    instruction: Annotated[str, Field(min_length=1, max_length=500)]


class MemoryWrite(Write):
    kind: Literal["exchange", "preference", "procedure"]
    text: Text
    key: Identifier | None = None
    source: Source = Field(default_factory=Source)
    visibility: Literal["private", "household"] = "private"
    occurredAt: int | None = Field(default=None, gt=0)
    validUntil: int | None = Field(default=None, gt=0)
    steps: list[ProcedureStep] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def representation(self):
        if self.kind in {"preference", "procedure"} and not self.key:
            raise ValueError("A stable key is required")
        if (self.kind == "procedure") != bool(self.steps):
            raise ValueError("Only a procedure has declarative steps")
        if len(self.model_dump_json().encode()) > 24000:
            raise ValueError("Memory content exceeds the canonical bound")
        return self


class MemoryPatch(Write):
    text: Text
    validUntil: int | None = Field(default=None, gt=0)
    visibility: Literal["private", "household"] = "private"
    steps: list[ProcedureStep] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def bounded(self):
        if len(self.model_dump_json().encode()) > 24000:
            raise ValueError("Memory content exceeds the canonical bound")
        return self


class ContextQuery(Write):
    includeCore: bool = False
    day: Annotated[str, Field(max_length=10)] | None = None
    key: Identifier | None = None
    query: Annotated[str, Field(min_length=1, max_length=1000)] | None = None
    limit: int = Field(default=8, ge=1, le=8)
    maxCharacters: int = Field(default=8000, ge=256, le=12000)

    @field_validator("day")
    @classmethod
    def date_or_yesterday(cls, value):
        if value and value != "yesterday":
            from datetime import date

            parsed = date.fromisoformat(value)
            if not date.min < parsed < date.max:
                raise ValueError("Context day must have representable timezone boundaries")
        return value


class MemorySearch(ContextQuery):
    includeCore: Literal[False] = False
    query: Annotated[str, Field(min_length=1, max_length=1000)]
    kinds: list[Literal["exchange", "preference", "procedure"]] = Field(
        default_factory=list, max_length=3
    )
    cursor: Annotated[str, Field(max_length=2048)] | None = None

    @field_validator("query")
    @classmethod
    def significant_query(cls, value):
        from koyori.lexical import query_terms

        query_terms(value)
        return value


class SimConnection(Write):
    provider: Literal["commerce-simulator"] = "commerce-simulator"


class BudgetPut(Write):
    currency: Literal["EUR"] = "EUR"
    limitMinor: int = Field(ge=0, le=10_000_000)
    perActionMinor: int = Field(ge=0, le=10_000_000)
    enabled: bool = True
    approvalRequired: bool = True


class Line(Write):
    sku: Literal["milk", "bread", "fruit", "vegetarian-meal", "chicken-meal"]
    quantity: int = Field(ge=1, le=20)


class QuoteCreate(Write):
    connectionId: Identifier
    capability: Literal["commerce.groceries", "commerce.meals"]
    intentionId: Identifier
    operation: Literal["create", "modify", "cancel"] = "create"
    targetActionId: Identifier | None = None
    lines: list[Line] = Field(default_factory=list, max_length=20)
    deliveryAt: int = Field(gt=0)

    @model_validator(mode="after")
    def operation_fields(self):
        if (self.operation == "create") != (self.targetActionId is None):
            raise ValueError("Modify/cancel must name a confirmed action")
        if (self.operation == "cancel") == bool(self.lines):
            raise ValueError("Only cancellation has no lines")
        if len({line.sku for line in self.lines}) != len(self.lines):
            raise ValueError("Duplicate lines")
        return self


class ApprovalCreate(Write):
    quoteId: Identifier


class ActionCreate(Write):
    quoteId: Identifier
    approvalId: Identifier | None = None


class CalendarAuthorize(Write):
    calendarIds: list[Annotated[str, Field(min_length=1, max_length=256)]] = Field(
        min_length=1, max_length=8
    )

    @field_validator("calendarIds")
    @classmethod
    def unique_ids(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Duplicate calendars")
        return value


class CalendarEventDraft(Write):
    connectionId: Identifier | None = None
    calendarId: Annotated[str, Field(min_length=1, max_length=256)] | None = None
    title: Annotated[str, Field(min_length=1, max_length=200)]
    startAt: int = Field(gt=0)
    endAt: int = Field(gt=0)
    location: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    notes: Annotated[str, Field(min_length=1, max_length=1000)] | None = None

    @model_validator(mode="after")
    def duration(self):
        if not 0 < self.endAt - self.startAt <= 14 * 86400:
            raise ValueError("An event lasts between one second and fourteen days")
        return self


class CalendarDecision(Write):
    decision: Literal["approve", "reject"]


class SupplierNotice(Write):
    eventId: Identifier
    householdId: Identifier
    actionId: Identifier
    occurredAt: int = Field(gt=0)
