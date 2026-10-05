"""HTTP contracts for explicit memory and connector commands, sharing stage-one identity."""

from typing import Annotated

from fastapi import Depends, Query, Request
from fastapi.responses import JSONResponse

from koyori.actions import CAPABILITIES, Actions
from koyori.calendar import Calendar
from koyori.domain import Context, projection
from koyori.memory import Memory
from koyori.security import expected_version
from koyori.semantic import Semantic
from koyori.stage2_contracts import (
    ActionCreate,
    ApprovalCreate,
    BudgetPut,
    CalendarAuthorize,
    ContextQuery,
    MemoryPatch,
    MemoryWrite,
    QuoteCreate,
    SimConnection,
    SupplierNotice,
)
from koyori.store import guard, put


def register(app, domain, actor, context):
    memory, actions, calendar, semantic = (
        Memory(domain),
        Actions(domain),
        Calendar(domain),
        Semantic(domain),
    )
    app.state.memory, app.state.actions, app.state.calendar, app.state.semantic = (
        memory,
        actions,
        calendar,
        semantic,
    )
    Ctx = Annotated[Context, Depends(context)]

    def mutation(service, request, ctx, body, work, *, version=None, authorize=None, protect=False):
        return service.mutate(
            ctx,
            f"{request.method} {request.url.path}",
            body,
            request.headers.get("Idempotency-Key"),
            version,
            request.headers.get("X-Step-Up-Grant"),
            work,
            authorize=authorize,
            protect=protect,
        )

    def result(value, status=200):
        return JSONResponse(
            value,
            status_code=status,
            headers={"ETag": f'"{value["rev"]}"'} if "rev" in value else {},
        )

    @app.get("/v1/memories")
    def memories(ctx: Ctx, cursor: Annotated[str | None, Query(max_length=2048)] = None):
        return memory.list(ctx, cursor)

    @app.post("/v1/memories", status_code=201)
    def create_memory(body: MemoryWrite, request: Request, ctx: Ctx):
        normalized = body.model_dump()
        saved = mutation(
            memory, request, ctx, normalized, lambda fresh: memory.create(fresh, normalized)
        )
        return result(projection(memory.get(ctx, saved["id"])), 201)

    @app.get("/v1/memories/{mid}")
    def get_memory(mid: str, ctx: Ctx):
        return result(projection(memory.get(ctx, mid)))

    @app.patch("/v1/memories/{mid}")
    def patch_memory(mid: str, body: MemoryPatch, request: Request, ctx: Ctx):
        normalized = body.model_dump(exclude_unset=True)
        version = expected_version(request.headers.get("If-Match"))
        mutation(
            memory,
            request,
            ctx,
            normalized,
            lambda fresh: memory.change(fresh, mid, normalized, version),
            version=version,
            authorize=lambda fresh: memory.get(fresh, mid, owner=True),
        )
        return result(projection(memory.get(ctx, mid)))

    @app.delete("/v1/memories/{mid}")
    def delete_memory(mid: str, request: Request, ctx: Ctx):
        version = expected_version(request.headers.get("If-Match"))
        saved = mutation(
            memory,
            request,
            ctx,
            {},
            lambda fresh: memory.change(fresh, mid, {}, version, delete=True),
            version=version,
            authorize=lambda fresh: memory.get(fresh, mid, owner=True, tombstone=True),
        )
        return result(saved)

    @app.post("/v1/context")
    def context_query(body: ContextQuery, ctx: Ctx):
        data = memory.context(
            ctx, body.model_dump(), semantic=semantic if semantic.mode != "disabled" else None
        )
        data["semanticMode"] = semantic.mode
        return data

    @app.get("/v1/commitments")
    def commitments(ctx: Ctx, cursor: Annotated[str | None, Query(max_length=2048)] = None):
        return memory.commitments(ctx, cursor)

    @app.get("/v1/capabilities")
    def capabilities(ctx: Ctx):
        return {
            "items": [
                {
                    **item,
                    "available": item["provider"] == "commerce-simulator"
                    or bool(
                        domain.settings.google_client_id and domain.settings.google_redirect_uri
                    ),
                }
                for item in CAPABILITIES
            ]
        }

    @app.post("/v1/connections/simulated", status_code=201)
    def connect_simulator(body: SimConnection, request: Request, ctx: Ctx):
        saved = mutation(actions, request, ctx, body.model_dump(), actions.connection)
        return result(actions.public(ctx, "CONNECTION", saved["id"]), 201)

    @app.get("/v1/connections")
    def connections(ctx: Ctx, cursor: Annotated[str | None, Query(max_length=2048)] = None):
        domain.personal(ctx)
        return domain.page(
            ctx,
            "Domain",
            "CONNECTION#",
            "connections",
            cursor,
            authorize=lambda item: actions.get(ctx, "CONNECTION", item["id"]),
        )

    @app.get("/v1/connections/{cid}")
    def connection(cid: str, ctx: Ctx):
        return result(actions.public(ctx, "CONNECTION", cid))

    @app.delete("/v1/connections/{cid}")
    def revoke_connection(cid: str, request: Request, ctx: Ctx):
        version = expected_version(request.headers.get("If-Match"))
        existing = actions.get(ctx, "CONNECTION", cid)
        service = calendar if existing["provider"] == "google-calendar" else actions
        saved = mutation(
            service,
            request,
            ctx,
            {},
            lambda fresh: service.revoke(fresh, cid, version),
            version=version,
            authorize=lambda fresh: actions.get(fresh, "CONNECTION", cid),
        )
        return result(saved)

    @app.post("/v1/connections/google-calendar/authorize", status_code=201)
    def authorize_calendar(body: CalendarAuthorize, request: Request, ctx: Ctx):
        normalized = body.model_dump()
        return result(
            mutation(
                calendar,
                request,
                ctx,
                normalized,
                lambda fresh: calendar.authorize(fresh, normalized),
                protect=True,
            ),
            201,
        )

    @app.get("/v1/oauth/google/callback")
    def google_callback(
        state: Annotated[str, Query(min_length=32, max_length=128)],
        code: Annotated[str, Query(min_length=1, max_length=2048)],
    ):
        return result(calendar.callback(state, code))

    @app.post("/v1/webhooks/google-calendar", status_code=204)
    def google_webhook(request: Request):
        calendar.webhook(dict(request.headers))
        from fastapi import Response

        return Response(status_code=204)

    @app.post("/v1/webhooks/commerce-simulator", status_code=204)
    def simulator_webhook(body: SupplierNotice, request: Request):
        actions.notify(body.model_dump(), request.headers.get("X-Koyori-Signature"))
        from fastapi import Response

        return Response(status_code=204)

    @app.post("/v1/connections/{cid}/sync", status_code=202)
    def synchronize(cid: str, request: Request, ctx: Ctx):
        def work(fresh):
            conn = calendar.get(fresh, cid)
            old = domain.store.get("Delivery", (f"CALRUN#{cid}", "META"))
            return (
                {"id": cid, "status": "PENDING"},
                [guard("Domain", conn), put("Delivery", calendar.intent(conn, old), old)],
                False,
            )

        return result(
            mutation(
                calendar, request, ctx, {}, work, authorize=lambda fresh: calendar.get(fresh, cid)
            ),
            202,
        )

    @app.get("/v1/connections/{cid}/events")
    def calendar_events(
        cid: str, ctx: Ctx, cursor: Annotated[str | None, Query(max_length=2048)] = None
    ):
        return calendar.events(ctx, cid, cursor)

    @app.get("/v1/budget")
    def budget(ctx: Ctx):
        return (
            result(projection(actions.budget(ctx)))
            if actions.budget(ctx)
            else {"rev": 0, "configured": False}
        )

    @app.put("/v1/budget")
    def put_budget(body: BudgetPut, request: Request, ctx: Ctx):
        normalized = body.model_dump()
        version = (
            0
            if request.headers.get("If-Match") == '"0"'
            else expected_version(request.headers.get("If-Match"))
        )
        mutation(
            actions,
            request,
            ctx,
            normalized,
            lambda fresh: actions.configure_budget(fresh, normalized, version),
            version=version,
        )
        return result(projection(actions.budget(ctx)))

    @app.post("/v1/quotes", status_code=201)
    def quote(body: QuoteCreate, request: Request, ctx: Ctx):
        normalized = body.model_dump()
        saved = mutation(
            actions, request, ctx, normalized, lambda fresh: actions.quote(fresh, normalized)
        )
        return result(actions.public(ctx, "QUOTE", saved["id"]), 201)

    @app.get("/v1/quotes/{qid}")
    def get_quote(qid: str, ctx: Ctx):
        return result(actions.public(ctx, "QUOTE", qid))

    @app.post("/v1/approvals", status_code=201)
    def approval(body: ApprovalCreate, request: Request, ctx: Ctx):
        normalized = body.model_dump()
        saved = mutation(
            actions, request, ctx, normalized, lambda fresh: actions.approve(fresh, body.quoteId)
        )
        return result(actions.public(ctx, "APPROVAL", saved["id"]), 201)

    @app.post("/v1/actions", status_code=202)
    def create_action(body: ActionCreate, request: Request, ctx: Ctx):
        normalized = body.model_dump()
        saved = mutation(
            actions, request, ctx, normalized, lambda fresh: actions.reserve(fresh, normalized)
        )
        return result(actions.public(ctx, "ACTION", saved["id"]), 202)

    @app.get("/v1/actions/{aid}")
    def get_action(aid: str, ctx: Ctx):
        return result(actions.public(ctx, "ACTION", aid))

    @app.get("/v1/actions")
    def list_actions(ctx: Ctx, cursor: Annotated[str | None, Query(max_length=2048)] = None):
        domain.personal(ctx)
        return domain.page(
            ctx,
            "Domain",
            "ACTION#",
            "actions",
            cursor,
            authorize=lambda item: actions.get(ctx, "ACTION", item["id"]),
        )
