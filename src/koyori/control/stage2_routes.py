"""HTTP contracts for explicit memory and connector commands, sharing stage-one identity."""

from typing import Annotated

from fastapi import Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from koyori.actions import CAPABILITIES, Actions
from koyori.agenda import Agenda
from koyori.calendar import Calendar
from koyori.domain import Context, projection
from koyori.errors import Problem
from koyori.memory import Memory
from koyori.security import expected_version
from koyori.semantic import Semantic
from koyori.stage2_contracts import (
    ActionCreate,
    ApprovalCreate,
    BudgetPut,
    CalendarAuthorize,
    CalendarDecision,
    CalendarEventDraft,
    ContextQuery,
    MemoryPatch,
    MemorySearch,
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
    app.state.agenda = agenda = Agenda(domain, calendar)
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
        return result(projection(memory.read(ctx, saved["id"])), 201)

    @app.post("/v1/memories/search")
    def search_memories(body: MemorySearch, ctx: Ctx):
        from koyori.lexical import Lexical

        return Lexical(domain).search(ctx, body.model_dump())

    @app.get("/v1/memories/{mid}")
    def get_memory(mid: str, ctx: Ctx):
        return result(projection(memory.read(ctx, mid)))

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
        return result(projection(memory.read(ctx, mid)))

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
        request: Request,
        state: Annotated[str, Query(min_length=32, max_length=128)],
        code: Annotated[str | None, Query(min_length=1, max_length=2048)] = None,
        error: Annotated[str | None, Query(max_length=128)] = None,
    ):
        # The consent popup is a browser page; API clients keep the JSON contract.
        page = "text/html" in request.headers.get("accept", "")
        try:
            if code is None:
                raise Problem(400, "OAUTH_DENIED", "Google consent was not granted.")
            connected = calendar.callback(state, code)
        except Problem as exc:
            if not page:
                raise
            return consent_page(
                "Connexion non terminée",
                "Annulée ou refusée. Fermez cette fenêtre et réessayez depuis Koyori."
                if exc.code == "OAUTH_DENIED"
                else "Google Agenda n’a pas pu être connecté. Fermez cette fenêtre et réessayez.",
                exc.status,
            )
        if not page:
            return result(connected)
        return consent_page(
            "Google Agenda connecté",
            "Vous pouvez fermer cette fenêtre et revenir à Koyori.",
            200,
        )

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

    @app.get("/v1/agenda")
    def upcoming(
        ctx: Ctx,
        start: Annotated[int, Query(alias="from", gt=0)],
        end: Annotated[int, Query(alias="to", gt=0)],
    ):
        domain.personal(ctx)
        return agenda.upcoming(ctx, start, end)

    @app.get("/v1/calendar-proposals")
    def calendar_proposals(ctx: Ctx, cursor: Annotated[str | None, Query(max_length=2048)] = None):
        domain.personal(ctx)
        return domain.page(
            ctx,
            "Domain",
            "CALPROPOSAL#",
            "calendar-proposals",
            cursor,
            authorize=lambda item: agenda.get(ctx, item["id"]),
        )

    @app.post("/v1/calendar-proposals", status_code=201)
    def propose_event(body: CalendarEventDraft, request: Request, ctx: Ctx):
        normalized = body.model_dump()
        saved = mutation(
            agenda,
            request,
            ctx,
            normalized,
            lambda fresh: agenda.propose(fresh, normalized, "person"),
        )
        return result(saved, 201)

    @app.post("/v1/calendar-proposals/{pid}/decision")
    def decide_event(pid: str, body: CalendarDecision, request: Request, ctx: Ctx):
        version = expected_version(request.headers.get("If-Match"))
        saved = mutation(
            agenda,
            request,
            ctx,
            body.model_dump(),
            lambda fresh: agenda.decide(fresh, pid, version, body.decision),
            version=version,
            authorize=lambda fresh: agenda.get(fresh, pid),
        )
        return result(saved)

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


def consent_page(title, message, status):
    """Static text only: nothing from the request or provider is echoed."""
    return HTMLResponse(
        f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:28rem;margin:4rem auto;padding:0 1rem;
color:#1f2328;background:#fbfaf7}}@media(prefers-color-scheme:dark){{body{{color:#ece8e1;
background:#191816}}}}</style></head><body><h1>{title}</h1><p>{message}</p></body></html>""",
        status_code=status,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )
