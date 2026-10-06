"""Protocol interoperability and resource-bound OAuth through the actual SDK transport."""

from uuid import uuid4

from koyori.demo import token
from koyori.mcp_server import RESERVED


def request(h, method, params=None, *, actor="alex", headers=None):
    return h.client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        headers={
            "Authorization": f"Bearer {token(h.settings, actor, mcp=True)}",
            "X-Household-Id": h.h,
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-11-25",
            **(headers or {}),
        },
    )


def test_initialize_discovery_no_approval_tools(harness):
    h = harness
    result = request(
        h,
        "initialize",
        {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["result"]["protocolVersion"] == "2025-11-25"
    discovery = request(h, "tools/list")
    names = {tool["name"] for tool in discovery.json()["result"]["tools"]}
    assert "submit_goal" in names
    assert not any("approval" in name or "grant" in name for name in names)
    assert all(
        tool["inputSchema"]["additionalProperties"] is False
        for tool in discovery.json()["result"]["tools"]
    )


def test_default_civil_day_follows_actor_timezone(harness):
    from datetime import datetime

    from koyori.channel_tools import ChannelTools
    from koyori.memory import Memory
    from koyori.sessions import Sessions
    from koyori.stage2_contracts import MemoryWrite
    from koyori.store import put, revised

    h = harness
    h.clock.value = int(datetime.fromisoformat("2026-10-05T20:30:00+00:00").timestamp())
    profile = h.domain.store.get("Domain", ("P#alex", "PROFILE"))
    h.domain.store.transact([put("Domain", revised(profile, timeZone="Asia/Tokyo"), profile)])
    ctx = h.domain.context("alex", h.h)
    saved, writes, _ = Memory(h.domain).create(
        ctx, MemoryWrite(kind="exchange", text="Tokyo civil day").model_dump()
    )
    h.domain.store.transact(ctx.guards() + writes)
    value = ChannelTools(h.domain).call(Sessions(h.domain).grant(ctx), "get_daily_context", {})
    assert value["timeZone"] == "Asia/Tokyo"
    assert any(item["id"] == saved["id"] for item in value["items"])


def test_resource_binding_scope_origins_and_headers(harness):
    h = harness
    control = request(h, "tools/list", headers={"Authorization": h.headers()["Authorization"]})
    assert control.status_code == 401
    assert "resource_metadata" in control.headers["WWW-Authenticate"]
    assert request(h, "tools/list", headers={"Origin": "https://evil.invalid"}).status_code == 403
    assert (
        request(h, "tools/list", headers={"MCP-Protocol-Version": "2024-11-05"}).status_code == 400
    )
    assert h.client.get("/mcp").status_code == 405
    assert (
        h.client.get("/.well-known/oauth-protected-resource/mcp").json()["resource"]
        == h.settings.mcp_resource
    )


def test_client_metadata_does_not_choose_identity_or_household(harness):
    h = harness
    private = h.command()
    result = request(
        h,
        "tools/call",
        {
            "name": "get_task_status",
            "arguments": {"taskId": private},
            "_meta": {RESERVED: "alex", "householdId": h.h},
        },
        actor="sam",
    )
    assert result.status_code == 200
    assert result.json()["result"]["isError"] is True
    assert "Synthetic checkpoint" not in result.text


def test_mutating_tool_idempotency_matches_rest_task(harness):
    h = harness
    args = {"text": "Prépare le dîner pour deux", "idempotencyKey": uuid4().hex}
    result = request(h, "tools/call", {"name": "submit_goal", "arguments": args})
    assert result.status_code == 200, result.text
    data = result.json()["result"]["structuredContent"]
    assert h.task(data["id"])["status"] == "READY"
    replay = request(h, "tools/call", {"name": "submit_goal", "arguments": args}).json()["result"][
        "structuredContent"
    ]
    assert replay["id"] == data["id"]
    invalid = request(
        h,
        "tools/call",
        {"name": "submit_goal", "arguments": {**args, "actor": "sam", "approval": True}},
    )
    assert invalid.json()["result"]["isError"] is True
    assert "sam" not in invalid.json()["result"]["content"][0]["text"]


def test_shared_mcp_task_read_and_personal_mutation_refused(harness):
    h = harness
    shared = h.command(visibility="household")
    result = request(
        h,
        "tools/call",
        {"name": "get_task_status", "arguments": {"taskId": shared}},
        actor="speaker",
    )
    assert result.json()["result"]["isError"] is False
    assert result.json()["result"]["structuredContent"]["id"] == shared
    refused = request(
        h,
        "tools/call",
        {"name": "submit_goal", "arguments": {"text": "Buy", "idempotencyKey": uuid4().hex}},
        actor="speaker",
    )
    assert refused.json()["result"]["isError"] is True
