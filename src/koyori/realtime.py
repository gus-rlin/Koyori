"""AppSync publishes only wake signals; authorized durable catch-up is authoritative."""

import json
from urllib.parse import urlparse

import boto3
import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

from koyori.domain import row
from koyori.errors import Conflict, Problem
from koyori.object_access import event_access
from koyori.sessions import Sessions
from koyori.stage2 import Service
from koyori.store import put


def signal_intent(domain, ctx, sequence):
    key = (f"SIGNAL#{ctx.h}#{ctx.actor}", "META")
    previous = domain.store.get("Delivery", key)
    item = row(
        *key,
        rev=(previous or {}).get("rev", 0) + 1,
        h=ctx.h,
        actor=ctx.actor,
        accessEpoch=ctx.member.get("accessEpoch", 1),
        sequence=sequence,
        status="PENDING",
        GSI1PK=f"SIGNAL#{sequence % domain.settings.shards}",
        GSI1SK=f"{domain.now():020d}#{ctx.actor}",
    )
    return put("Delivery", item, previous)


class Signals(Service):
    def subscribe(self, ctx):
        self.domain.personal(ctx)
        secret = Sessions(self.domain).grant(ctx, tools=[])
        return {
            "protocol": "aws-appsync-event-ws",
            "url": self.domain.settings.realtime_url,
            "channel": f"/activity/{ctx.h}/{ctx.actor}",
            "authorizationToken": secret,
            "expiresAt": self.domain.now() + 30,
            "durableCatchup": "/v1/activity/catchup",
            "mode": "aws" if self.domain.settings.realtime_url else "polling",
        }

    def authorize(self, event):
        try:
            token = event.get("authorizationToken", "")
            if not isinstance(token, str) or len(token) != 43:
                return {"isAuthorized": False}
            ctx, checks = Sessions(self.domain).resolve(token)
            operation = event.get("requestContext", {}).get("operation")
            path = event.get("requestContext", {}).get("channel")
            expected = f"/activity/{ctx.h}/{ctx.actor}"
            if (
                operation not in {"EVENT_CONNECT", "EVENT_SUBSCRIBE"}
                or operation == "EVENT_SUBSCRIBE"
                and path != expected
            ):
                return {"isAuthorized": False}
            self.store.transact(ctx.guards() + checks)
            return {
                "isAuthorized": True,
                "handlerContext": {"householdId": ctx.h, "actorId": ctx.actor},
                "ttlOverride": 0,
            }
        except (Problem, Conflict, TypeError, KeyError):
            return {"isAuthorized": False}

    def catchup(self, ctx, after=0):
        self.domain.personal(ctx)
        pk = f"FEED#{ctx.h}#{ctx.actor}"
        key = {"PK": pk, "SK": f"SEQ#{after:020d}"} if after else None
        records, last = self.store.query("Delivery", pk, prefix="SEQ#", after=key, limit=20)
        values, checks = [], []
        for item in records:
            try:
                if item["type"] == "koyori.task.changed.v1":
                    _, access = self.domain.task_access(ctx, item["aggregateId"])
                else:
                    access = event_access(self.domain, ctx, item["type"], item["aggregateId"])
                checks.extend(access)
                values.append({k: v for k, v in item.items() if k not in {"PK", "SK", "rev"}})
            except Problem as exc:
                if exc.status not in {403, 404}:
                    raise
        self.store.transact(ctx.guards() + checks)
        return {
            "items": values,
            "nextAfter": records[-1]["sequence"] if records else after,
            "hasMore": bool(last),
        }

    def publish(self, item):
        settings = self.domain.settings
        if not settings.realtime_url:
            return  # Local polling retains the same durable feed.
        url = (
            settings.realtime_url.replace("wss://", "https://")
            .replace("-realtime-api.", "-api.")
            .removesuffix("/event/realtime")
            + "/event"
        )
        host = urlparse(url).hostname
        if not host or not host.endswith(f".appsync-api.{settings.region}.amazonaws.com"):
            raise Problem(503, "INVALID_REALTIME_ENDPOINT", "Unexpected AppSync endpoint.")
        body = json.dumps(
            {
                "channel": f"/activity/{item['h']}/{item['actor']}",
                "events": [
                    json.dumps({"type": "activity.available", "sequence": item["sequence"]})
                ],
            }
        ).encode()
        session = boto3.Session(region_name=settings.region)
        credentials = session.get_credentials().get_frozen_credentials()
        request = AWSRequest(
            method="POST", url=url, data=body, headers={"Content-Type": "application/json"}
        )
        SigV4Auth(credentials, "appsync", settings.region).add_auth(request)
        with httpx.Client(timeout=5) as client:
            response = client.post(url, content=body, headers=dict(request.headers))
        if response.status_code != 200 or response.json().get("failed"):
            raise Problem(502, "REALTIME_PUBLISH_FAILED", "Realtime signal is pending.", True)

    def sweep(self):
        for candidate in self.pending("SIGNAL"):
            item = self.store.get("Delivery", (candidate["PK"], "META"))
            if item["status"] != "PENDING":
                continue
            try:
                ctx = self.domain.context(item["actor"], item["h"])
                if ctx.member.get("accessEpoch", 1) == item["accessEpoch"]:
                    self.publish(item)
            except Problem as exc:
                if exc.status != 403:
                    raise
            try:
                self.store.transact([put("Delivery", self.domain.done_intent(item), item)])
            except Conflict:
                continue  # A newer durable high-water signal remains pending.


def authorizer(event, context):
    from koyori.workers.runtime import engine

    return Signals(engine().domain).authorize(event)


def tick(event=None, context=None):
    from koyori.privacy import Privacy
    from koyori.workers.runtime import engine

    domain = engine().domain
    Privacy(domain).sweep()
    Signals(domain).sweep()
    return {"status": "RECONCILED"}
