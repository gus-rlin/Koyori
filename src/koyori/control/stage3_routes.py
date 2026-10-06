"""Goal, routine, learning and notification APIs over the same authenticated context."""

from typing import Annotated

from fastapi import Depends, Query, Request
from fastapi.responses import JSONResponse

from koyori.domain import Context, projection
from koyori.goals import Goals
from koyori.learning import Learning
from koyori.notifications import Notifications
from koyori.scheduling import Wakes
from koyori.security import expected_version
from koyori.stage3_contracts import (
    GoalDecision,
    GoalSubmit,
    LearningDecision,
    LearningSubmit,
    NotificationPolicy,
    RoutineWrite,
)


def register(app, domain, context):
    goals, wakes, learning, notifications = (
        Goals(domain),
        Wakes(domain),
        Learning(domain),
        Notifications(domain),
    )
    app.state.goals, app.state.wakes, app.state.learning, app.state.notifications = (
        goals,
        wakes,
        learning,
        notifications,
    )
    Ctx = Annotated[Context, Depends(context)]

    def result(value, status=200):
        return JSONResponse(
            value,
            status_code=status,
            headers={"ETag": f'"{value["rev"]}"'} if "rev" in value else {},
        )

    def mutation(service, request, ctx, body, work, *, version=None, authorize=None):
        return service.mutate(
            ctx,
            f"{request.method} {request.url.path}",
            body,
            request.headers.get("Idempotency-Key"),
            version,
            None,
            work,
            authorize=authorize,
        )

    @app.post("/v1/goals", status_code=202)
    def submit_goal(body: GoalSubmit, request: Request, ctx: Ctx):
        normalized = body.model_dump()
        saved = mutation(
            goals, request, ctx, normalized, lambda fresh: goals.create(fresh, normalized)
        )
        return result(goals.public(ctx, saved["id"]), 202)

    @app.get("/v1/goals")
    def list_goals(ctx: Ctx, cursor: Annotated[str | None, Query(max_length=2048)] = None):
        domain.personal(ctx)
        return domain.page(
            ctx,
            "Domain",
            "TASK#",
            "goals",
            cursor,
            authorize=lambda item: goals.public(ctx, item["id"]),
        )

    @app.get("/v1/goals/{tid}")
    def get_goal(tid: str, ctx: Ctx):
        return result(goals.public(ctx, tid))

    @app.patch("/v1/goals/{tid}")
    def amend_goal(tid: str, body: GoalSubmit, request: Request, ctx: Ctx):
        normalized = body.model_dump()
        version = expected_version(request.headers.get("If-Match"))
        mutation(
            goals,
            request,
            ctx,
            normalized,
            lambda fresh: goals.change(fresh, tid, normalized, version, "amend"),
            version=version,
            authorize=lambda fresh: goals.get(fresh, tid),
        )
        return result(goals.public(ctx, tid))

    def goal_control(tid, request, ctx, action):
        version = expected_version(request.headers.get("If-Match"))
        mutation(
            goals,
            request,
            ctx,
            {},
            lambda fresh: goals.change(fresh, tid, {}, version, action),
            version=version,
            authorize=lambda fresh: goals.get(fresh, tid),
        )
        return result(goals.public(ctx, tid), 202)

    @app.post("/v1/goals/{tid}/pause", status_code=202)
    def pause_goal(tid: str, request: Request, ctx: Ctx):
        return goal_control(tid, request, ctx, "pause")

    @app.post("/v1/goals/{tid}/resume", status_code=202)
    def resume_goal(tid: str, request: Request, ctx: Ctx):
        return goal_control(tid, request, ctx, "resume")

    @app.post("/v1/goals/{tid}/cancel", status_code=202)
    def cancel_goal(tid: str, request: Request, ctx: Ctx):
        return goal_control(tid, request, ctx, "cancel")

    @app.post("/v1/goals/{tid}/decisions", status_code=202)
    def goal_decision(tid: str, body: GoalDecision, request: Request, ctx: Ctx):
        normalized = body.model_dump()
        version = expected_version(request.headers.get("If-Match"))
        mutation(
            goals,
            request,
            ctx,
            normalized,
            lambda fresh: goals.decide(fresh, tid, normalized, version),
            version=version,
            authorize=lambda fresh: goals.get(fresh, tid),
        )
        return result(goals.public(ctx, tid), 202)

    @app.post("/v1/routines", status_code=201)
    def create_routine(body: RoutineWrite, request: Request, ctx: Ctx):
        normalized = body.model_dump()
        saved = mutation(
            wakes, request, ctx, normalized, lambda fresh: wakes.create_rule(fresh, normalized)
        )
        return result(projection(wakes.get_rule(ctx, saved["id"])), 201)

    @app.get("/v1/routines")
    def list_routines(ctx: Ctx, cursor: Annotated[str | None, Query(max_length=2048)] = None):
        domain.personal(ctx)
        return domain.page(
            ctx,
            "Domain",
            "ROUTINE#",
            "routines",
            cursor,
            authorize=lambda item: projection(wakes.get_rule(ctx, item["id"])),
        )

    @app.get("/v1/routines/{rid}")
    def get_routine(rid: str, ctx: Ctx):
        return result(projection(wakes.get_rule(ctx, rid)))

    @app.patch("/v1/routines/{rid}")
    def amend_routine(rid: str, body: RoutineWrite, request: Request, ctx: Ctx):
        normalized = body.model_dump()
        version = expected_version(request.headers.get("If-Match"))
        mutation(
            wakes,
            request,
            ctx,
            normalized,
            lambda fresh: wakes.change_rule(fresh, rid, normalized, version, "amend"),
            version=version,
            authorize=lambda fresh: wakes.get_rule(fresh, rid),
        )
        return result(projection(wakes.get_rule(ctx, rid)))

    def routine_control(rid, request, ctx, action):
        version = expected_version(request.headers.get("If-Match"))
        mutation(
            wakes,
            request,
            ctx,
            {},
            lambda fresh: wakes.change_rule(fresh, rid, {}, version, action),
            version=version,
            authorize=lambda fresh: wakes.get_rule(fresh, rid),
        )
        return result(projection(wakes.get_rule(ctx, rid)))

    @app.post("/v1/routines/{rid}/pause")
    def pause_routine(rid: str, request: Request, ctx: Ctx):
        return routine_control(rid, request, ctx, "pause")

    @app.post("/v1/routines/{rid}/resume")
    def resume_routine(rid: str, request: Request, ctx: Ctx):
        return routine_control(rid, request, ctx, "resume")

    @app.delete("/v1/routines/{rid}")
    def cancel_routine(rid: str, request: Request, ctx: Ctx):
        return routine_control(rid, request, ctx, "cancel")

    @app.post("/v1/learning", status_code=201)
    def propose_learning(body: LearningSubmit, request: Request, ctx: Ctx):
        normalized = body.model_dump()
        saved = mutation(
            learning, request, ctx, normalized, lambda fresh: learning.propose(fresh, normalized)
        )
        return result(learning.public(ctx, saved["id"]), 201)

    @app.get("/v1/learning")
    def list_learning(ctx: Ctx, cursor: Annotated[str | None, Query(max_length=2048)] = None):
        domain.personal(ctx)
        return domain.page(
            ctx,
            "Domain",
            "LEARNING#",
            "learning",
            cursor,
            authorize=lambda item: learning.public(ctx, item["id"]),
        )

    @app.get("/v1/learning/{identifier}")
    def get_learning(identifier: str, ctx: Ctx):
        return result(learning.public(ctx, identifier))

    @app.post("/v1/learning/{identifier}/decisions")
    def decide_learning(identifier: str, body: LearningDecision, request: Request, ctx: Ctx):
        normalized = body.model_dump()
        version = expected_version(request.headers.get("If-Match"))
        mutation(
            learning,
            request,
            ctx,
            normalized,
            lambda fresh: learning.decide(fresh, identifier, normalized, version),
            version=version,
            authorize=lambda fresh: learning.get(fresh, identifier),
        )
        return result(learning.public(ctx, identifier))

    @app.get("/v1/notification-policy")
    def notification_policy(ctx: Ctx):
        domain.personal(ctx)
        current = notifications.policy(ctx)
        return result(
            projection(current)
            if current
            else {"rev": 0, **NotificationPolicy(timeZone=ctx.household["timeZone"]).model_dump()}
        )

    @app.put("/v1/notification-policy")
    def configure_notifications(body: NotificationPolicy, request: Request, ctx: Ctx):
        normalized = body.model_dump()
        version = (
            0
            if request.headers.get("If-Match") == '"0"'
            else expected_version(request.headers.get("If-Match"))
        )
        mutation(
            notifications,
            request,
            ctx,
            normalized,
            lambda fresh: notifications.configure(fresh, normalized, version),
            version=version,
        )
        return result(projection(notifications.policy(ctx)))

    @app.get("/v1/notifications")
    def list_notifications(ctx: Ctx, cursor: Annotated[str | None, Query(max_length=2048)] = None):
        return notifications.list(ctx, cursor)
