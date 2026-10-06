"""Authoritative HTTP control surface. Dependency errors are redacted at ingress."""

import json
import logging
import re
import time
import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from koyori.config import Settings
from koyori.contracts import (
    Command,
    DelegationCreate,
    HouseholdCreate,
    MemberCreate,
    MemberPatch,
    PolicyPut,
    StepUpComplete,
    StepUpCreate,
    TaskPatch,
)
from koyori.domain import Context, Domain, projection
from koyori.errors import Problem
from koyori.security import Cursors, Tokens, expected_version
from koyori.store import DynamoStore

LOG = logging.getLogger("koyori.http")
ID_PATTERN = r"^[A-Za-z0-9_-]{1,128}$"


def create_app(*, domain: Domain | None = None, tokens: Tokens | None = None) -> FastAPI:
    if domain is None:
        settings = Settings.from_env()
        domain = Domain(DynamoStore(settings), settings, Cursors(settings.cursor_secret()))
    tokens = tokens or Tokens(domain.settings)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    app = FastAPI(
        title="Koyori — durable control API",
        version="0.1.0",
        docs_url="/docs" if domain.settings.env == "local" else None,
        redoc_url=None,
    )
    app.state.domain = domain

    def problem_response(request: Request, exc: Problem):
        headers = {"Cache-Control": "no-store"}
        if exc.status == 401:
            headers["WWW-Authenticate"] = "Bearer"
        if exc.status in {429, 503}:
            headers["Retry-After"] = "2"
        return JSONResponse(
            dict(
                type=f"urn:koyori:problem:{exc.code.lower().replace('_', '-')}",
                title=exc.code,
                status=exc.status,
                code=exc.code,
                detail=exc.detail,
                retryable=exc.retryable,
                requestId=getattr(request.state, "request_id", "unavailable"),
            ),
            status_code=exc.status,
            media_type="application/problem+json",
            headers=headers,
        )

    @app.exception_handler(Problem)
    async def known(request, exc):
        return problem_response(request, exc)

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        # Validation input may contain passwords/tokens; never serialize exc.errors().
        return problem_response(
            request, Problem(422, "INVALID_REQUEST", "Request fields are invalid or unsupported.")
        )

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        response = problem_response(
            request, Problem(exc.status_code, "HTTP_ERROR", "Request unavailable.")
        )
        response.headers.update(exc.headers or {})
        return response

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex
        start = time.monotonic()
        try:
            restore = domain.store.get("Sessions", ("RESTORE_FENCE", "META"))
            if (
                request.method in {"POST", "PATCH", "PUT", "DELETE"}
                and restore
                and restore.get("blocked")
            ):
                raise Problem(
                    503, "RESTORE_OFFLINE", "Restored namespace awaits operator reconciliation."
                )
            # Read the stream with a hard bound even if Content-Length is missing or forged.
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 32768:
                    raise Problem(413, "REQUEST_TOO_LARGE", "Request exceeds 32 KiB.")
                chunks.append(chunk)
            request._body = b"".join(chunks)
            if request.method == "DELETE" or request.url.path.endswith(
                ("/pause", "/resume", "/cancel", "/sync")
            ):
                if request._body.strip():
                    try:
                        payload = json.loads(request._body)
                        if payload not in ({}, {"schemaVersion": "1.0"}):
                            raise ValueError
                    except (ValueError, UnicodeDecodeError):
                        raise Problem(
                            422,
                            "INVALID_REQUEST",
                            "This operation accepts no business arguments.",
                        ) from None
            response = await call_next(request)
        except Problem as exc:
            response = problem_response(request, exc)
        except Exception as exc:
            LOG.error(
                json.dumps(
                    {
                        "event": "request_failed",
                        "requestId": request.state.request_id,
                        "errorClass": type(exc).__name__,
                    }
                )
            )
            response = problem_response(
                request,
                Problem(503, "DEPENDENCY_UNAVAILABLE", "Service temporarily unavailable.", True),
            )
        response.headers["X-Request-Id"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        route = request.scope.get("route")
        LOG.info(
            json.dumps(
                {
                    "event": "http",
                    "requestId": request.state.request_id,
                    "route": getattr(route, "path", "unmatched"),
                    "method": request.method,
                    "status": response.status_code,
                    "durationMs": int((time.monotonic() - start) * 1000),
                }
            )
        )
        return response

    def actor(authorization: Annotated[str | None, Header()] = None) -> str:
        return tokens.bearer(authorization)

    def household(x_household_id: Annotated[str | None, Header()] = None) -> str:
        if not x_household_id or not re.fullmatch(ID_PATTERN, x_household_id):
            raise Problem(400, "HOUSEHOLD_REQUIRED", "A valid X-Household-Id selector is required.")
        return x_household_id

    def context(principal: Annotated[str, Depends(actor)], h: Annotated[str, Depends(household)]):
        return domain.context(principal, h)

    def mutation(request: Request, ctx, body, work, *, version=None, auth="personal", target=None):
        return domain.mutate(
            ctx.actor,
            ctx.h,
            f"{request.method} {request.url.path}",
            body,
            request.headers.get("Idempotency-Key"),
            version,
            request.headers.get("X-Step-Up-Grant"),
            work,
            auth=auth,
            target=target,
        )

    def result(value: dict, status=200):
        headers = {"ETag": f'"{value["rev"]}"'} if "rev" in value else {}
        return JSONResponse(value, status_code=status, headers=headers)

    @app.get("/health/live")
    def live():
        return {"status": "alive", "stage": 2}

    @app.get("/health/ready")
    def ready():
        domain.store.get("Domain", ("HEALTH", "META"))
        return {"status": "ready", "mode": "sandbox"}

    @app.get("/v1/households")
    def households(
        principal: Annotated[str, Depends(actor)],
        cursor: Annotated[str | None, Query(max_length=2048)] = None,
    ):
        route = "households"
        after = domain.cursors.decode(cursor, principal, "", route)
        links, last = domain.store.query(
            "Domain", f"P#{principal}", prefix="H#", after=after, limit=50
        )
        items = []
        for link in links:
            try:
                items.append(projection(domain.context(principal, link["householdId"]).household))
            except Problem as exc:
                if exc.status != 403:
                    raise
        return {
            "items": items,
            "nextCursor": domain.cursors.encode(principal, "", route, last) if last else None,
        }

    @app.post("/v1/households", status_code=201)
    def create_household(
        body: HouseholdCreate, request: Request, principal: Annotated[str, Depends(actor)]
    ):
        return result(
            domain.create_household(
                principal, body.model_dump(), request.headers.get("Idempotency-Key")
            ),
            201,
        )

    @app.get("/v1/households/{hid}/members")
    def members(
        hid: str,
        principal: Annotated[str, Depends(actor)],
        cursor: Annotated[str | None, Query(max_length=2048)] = None,
    ):
        ctx = domain.context(principal, hid)
        domain.admin(ctx)
        return domain.page(ctx, "Domain", "MEMBER#", "members", cursor)

    @app.post("/v1/households/{hid}/members", status_code=201)
    def add_member(
        hid: str, body: MemberCreate, request: Request, principal: Annotated[str, Depends(actor)]
    ):
        ctx = domain.context(principal, hid)
        normalized = body.model_dump()
        return result(
            mutation(
                request,
                ctx,
                normalized,
                lambda fresh: domain.add_member(fresh, normalized),
                auth="admin",
            ),
            201,
        )

    @app.patch("/v1/households/{hid}/members/{pid}")
    def patch_member(
        hid: str,
        pid: str,
        body: MemberPatch,
        request: Request,
        principal: Annotated[str, Depends(actor)],
    ):
        ctx = domain.context(principal, hid)
        version = expected_version(request.headers.get("If-Match"))
        normalized = body.model_dump(exclude_unset=True)
        if not any(k in normalized for k in ("role", "expiresAt")):
            raise Problem(422, "EMPTY_PATCH", "Provide membership fields.")
        return result(
            mutation(
                request,
                ctx,
                normalized,
                lambda fresh: domain.change_member(fresh, pid, normalized, version, revoke=False),
                version=version,
                auth="admin",
            )
        )

    @app.delete("/v1/households/{hid}/members/{pid}")
    def revoke_member(
        hid: str, pid: str, request: Request, principal: Annotated[str, Depends(actor)]
    ):
        ctx = domain.context(principal, hid)
        version = expected_version(request.headers.get("If-Match"))
        return result(
            mutation(
                request,
                ctx,
                {},
                lambda fresh: domain.change_member(fresh, pid, {}, version, revoke=True),
                version=version,
                auth="admin",
            )
        )

    @app.post("/v1/commands", status_code=202)
    def command(body: Command, request: Request, ctx: Annotated[Context, Depends(context)]):
        normalized = body.model_dump()
        return result(
            mutation(request, ctx, normalized, lambda fresh: domain.command(fresh, normalized)), 202
        )

    @app.get("/v1/tasks")
    def tasks(
        ctx: Annotated[Context, Depends(context)],
        cursor: Annotated[str | None, Query(max_length=2048)] = None,
    ):
        return domain.page(
            ctx,
            "Domain",
            "TASK#",
            "tasks",
            cursor,
            authorize=lambda item: domain.task_access(ctx, item["id"])[0],
        )

    @app.get("/v1/tasks/{tid}")
    def task(tid: str, ctx: Annotated[Context, Depends(context)]):
        return result(projection(domain.task_access(ctx, tid)[0]))

    @app.patch("/v1/tasks/{tid}", status_code=202)
    def patch_task(
        tid: str, body: TaskPatch, request: Request, ctx: Annotated[Context, Depends(context)]
    ):
        normalized = body.model_dump()
        version = expected_version(request.headers.get("If-Match"))
        return result(
            mutation(
                request,
                ctx,
                normalized,
                lambda fresh: domain.change_task(fresh, tid, normalized, version, "amend"),
                version=version,
                auth="control",
                target=tid,
            ),
            202,
        )

    def transition(tid, request, ctx, action):
        version = expected_version(request.headers.get("If-Match"))
        return result(
            mutation(
                request,
                ctx,
                {},
                lambda fresh: domain.change_task(fresh, tid, {}, version, action),
                version=version,
                auth="control",
                target=tid,
            ),
            202,
        )

    @app.post("/v1/tasks/{tid}/pause", status_code=202)
    def pause(tid: str, request: Request, ctx: Annotated[Context, Depends(context)]):
        return transition(tid, request, ctx, "pause")

    @app.post("/v1/tasks/{tid}/resume", status_code=202)
    def resume(tid: str, request: Request, ctx: Annotated[Context, Depends(context)]):
        return transition(tid, request, ctx, "resume")

    @app.post("/v1/tasks/{tid}/cancel", status_code=202)
    def cancel(tid: str, request: Request, ctx: Annotated[Context, Depends(context)]):
        return transition(tid, request, ctx, "cancel")

    @app.get("/v1/tasks/{tid}/delegations")
    def delegations(
        tid: str,
        ctx: Annotated[Context, Depends(context)],
        cursor: Annotated[str | None, Query(max_length=2048)] = None,
    ):
        domain.task_access(ctx, tid, "owner")
        return domain.page(ctx, "Domain", f"DELEGATION#{tid}#", f"delegations/{tid}", cursor)

    @app.post("/v1/tasks/{tid}/delegations", status_code=201)
    def delegate(
        tid: str,
        body: DelegationCreate,
        request: Request,
        ctx: Annotated[Context, Depends(context)],
    ):
        normalized = body.model_dump()
        return result(
            mutation(
                request,
                ctx,
                normalized,
                lambda fresh: domain.delegate(fresh, tid, normalized),
                auth="owner",
                target=tid,
            ),
            201,
        )

    @app.delete("/v1/tasks/{tid}/delegations/{did}")
    def revoke_delegation(
        tid: str, did: str, request: Request, ctx: Annotated[Context, Depends(context)]
    ):
        version = expected_version(request.headers.get("If-Match"))
        return result(
            mutation(
                request,
                ctx,
                {},
                lambda fresh: domain.revoke_delegation(fresh, tid, did, version),
                version=version,
                auth="owner",
                target=tid,
            )
        )

    @app.get("/v1/policies")
    def policies(ctx: Annotated[Context, Depends(context)]):
        domain.admin(ctx)
        return domain.page(ctx, "Domain", "POLICY#", "policies", None)

    @app.put("/v1/policies/{pid}")
    def policy(
        pid: str, body: PolicyPut, request: Request, ctx: Annotated[Context, Depends(context)]
    ):
        version = expected_version(request.headers.get("If-Match"))
        normalized = body.model_dump()
        return result(
            mutation(
                request,
                ctx,
                normalized,
                lambda fresh: domain.policy(fresh, pid, normalized, version),
                version=version,
                auth="admin",
            )
        )

    @app.post("/v1/auth/step-up", status_code=201)
    def challenge(body: StepUpCreate, request: Request, ctx: Annotated[Context, Depends(context)]):
        return result(
            domain.challenge(
                ctx.actor, ctx.h, body.model_dump(), request.headers.get("Idempotency-Key")
            ),
            201,
        )

    @app.post("/v1/auth/step-up/{cid}/complete")
    def complete_challenge(
        cid: str, body: StepUpComplete, request: Request, ctx: Annotated[Context, Depends(context)]
    ):
        return domain.complete_challenge(
            ctx.actor, ctx.h, cid, body.model_dump(), request.headers.get("Idempotency-Key"), tokens
        )

    @app.get("/v1/activity")
    def activity(
        ctx: Annotated[Context, Depends(context)],
        cursor: Annotated[str | None, Query(max_length=2048)] = None,
    ):
        def authorize(item):
            if item["type"] == "koyori.task.changed.v1":
                domain.task_access(ctx, item["aggregateId"])
            else:
                try:
                    from koyori.object_access import event_access

                    event_access(domain, ctx, item["type"], item["aggregateId"])
                except Problem:
                    return None
            return item

        return domain.page(
            ctx,
            "Delivery",
            "SEQ#",
            "activity",
            cursor,
            pk=f"FEED#{ctx.h}#{ctx.actor}",
            authorize=authorize,
        )

    from koyori.control.stage2_routes import register

    register(app, domain, actor, context)
    from koyori.control.stage3_routes import register as register_stage3

    register_stage3(app, domain, context)
    from koyori.control.stage4_routes import register as register_stage4

    register_stage4(app, domain, tokens, context)
    return app
