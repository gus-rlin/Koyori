"""REST admission, MCP, scoped catch-up and explicit personal privacy controls."""

from typing import Annotated

from fastapi import Depends, Query, Request
from fastapi.responses import JSONResponse

from koyori.domain import Context
from koyori.mcp_server import MCPTransport
from koyori.privacy import Privacy
from koyori.realtime import Signals
from koyori.sessions import Sessions
from koyori.stage4_contracts import MemoryErase, SessionCreate


def register(app, domain, tokens, context):
    sessions, privacy, signals = Sessions(domain), Privacy(domain), Signals(domain)
    transport = MCPTransport(domain, tokens, goals=app.state.goals)
    app.state.sessions, app.state.privacy, app.state.signals, app.state.mcp = (
        sessions,
        privacy,
        signals,
        transport,
    )
    Ctx = Annotated[Context, Depends(context)]

    @app.post("/v1/sessions", status_code=201)
    def admit(body: SessionCreate, ctx: Ctx):
        return JSONResponse(
            sessions.issue(ctx, body.model_dump()), 201, headers={"Cache-Control": "no-store"}
        )

    @app.api_route("/mcp", methods=["GET", "POST", "DELETE"])
    async def mcp(request: Request):
        return await transport.handle(request)

    @app.get("/.well-known/oauth-protected-resource/mcp")
    def resource():
        return {
            "resource": domain.settings.mcp_resource,
            "authorization_servers": [domain.settings.issuer],
            "scopes_supported": ["koyori/mcp"],
            "bearer_methods_supported": ["header"],
        }

    @app.post("/v1/activity/subscription", status_code=201)
    def subscription(ctx: Ctx):
        return JSONResponse(signals.subscribe(ctx), 201, headers={"Cache-Control": "no-store"})

    @app.get("/v1/activity/catchup")
    def catchup(ctx: Ctx, after: Annotated[int, Query(ge=0, le=10**12)] = 0):
        return signals.catchup(ctx, after)

    @app.get("/v1/privacy/export")
    def export(ctx: Ctx, cursor: Annotated[str | None, Query(max_length=2048)] = None):
        return JSONResponse(privacy.export(ctx, cursor), headers={"Cache-Control": "no-store"})

    @app.post("/v1/privacy/memories/erase", status_code=202)
    def erase(body: MemoryErase, request: Request, ctx: Ctx):
        saved = privacy.mutate(
            ctx,
            "POST /v1/privacy/memories/erase",
            body.model_dump(),
            request.headers.get("Idempotency-Key"),
            None,
            request.headers.get("X-Step-Up-Grant"),
            privacy.start,
        )
        return JSONResponse(
            privacy.get(ctx, saved["id"]), 202, headers={"Cache-Control": "no-store"}
        )

    @app.get("/v1/privacy/erasures/{identifier}")
    def erasure(identifier: str, ctx: Ctx):
        return privacy.get(ctx, identifier)
