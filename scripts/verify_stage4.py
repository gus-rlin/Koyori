"""Observable Docker MCP/voice/reconnect recipe with synthetic finalized transcripts."""

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from verify_local import BASE, ROOT, compose, demo_household, wait_ready
from websockets.asyncio.client import connect


def main():
    wait_ready()
    access = compose(
        "run", "--rm", "--no-deps", "demo", "python", "-m", "koyori.demo", "token", "alex"
    ).strip()
    mcp_access = compose(
        "run", "--rm", "--no-deps", "demo", "python", "-m", "koyori.demo", "token", "alex", "--mcp"
    ).strip()
    client = httpx.Client(base_url=BASE, timeout=10, headers={"Authorization": f"Bearer {access}"})
    h = demo_household(client)["id"]
    client.headers["X-Household-Id"] = h
    measurements = []
    checks = {}
    stopped = ["coordinator", "workflow", "repair", "scheduler"]

    def rpc(method, params):
        start = time.perf_counter()
        result = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            headers={
                "Authorization": f"Bearer {mcp_access}",
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": "2025-11-25",
            },
        )
        measurements.append((time.perf_counter() - start) * 1000)
        assert result.status_code == 200, result.status_code
        result = result.json()["result"]
        assert not result.get("isError"), result.get("isError")
        return result.get("structuredContent", result)

    async def voice(grant, text=None):
        start = time.perf_counter()
        async with connect(grant["connectionUrl"], max_size=65536, max_queue=4) as ws:
            await ws.send(
                json.dumps(
                    {
                        "type": "session.bootstrap",
                        "protocolVersion": "1.0",
                        "runtimeSessionId": grant["runtimeSessionId"],
                        "ticket": grant["ticket"],
                    }
                )
            )
            ready = json.loads(await asyncio.wait_for(ws.recv(), 5))
            assert ready["type"] == "session.ready", ready.get("type")
            measurements.append((time.perf_counter() - start) * 1000)
            if text:
                await ws.send(
                    json.dumps({"type": "turn.final", "turnId": uuid4().hex, "text": text})
                )
                finalized = json.loads(await asyncio.wait_for(ws.recv(), 5))
                assert finalized["type"] == "turn.finalized", finalized.get("type")
                # Abrupt close immediately after durable acceptance.
                return finalized["taskId"]
            await ws.send(json.dumps({"type": "session.close"}))

    def catchup_contains(identifier):
        after = 0
        for _ in range(100):
            response = client.get("/v1/activity/catchup", params={"after": after})
            assert response.status_code == 200
            feed = response.json()
            if any(item["aggregateId"] == identifier for item in feed["items"]):
                return True
            if not feed["hasMore"]:
                return False
            after = feed["nextAfter"]
        raise AssertionError("Catch-up exceeded the bounded fixture window")

    try:
        rpc(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "qualification", "version": "1"},
            },
        )
        checks["officialMcpInitialize"] = True
        compose("stop", *stopped)
        grant = client.post(
            "/v1/sessions", json={"mode": "personal", "microphoneConsent": True}
        ).json()
        tid = asyncio.run(voice(grant, "Rappelle mes préférences de dîner"))
        assert (
            rpc("tools/call", {"name": "get_task_status", "arguments": {"taskId": tid}})["id"]
            == tid
        )
        checks["voiceMcpAndRestSameTask"] = True
        compose("restart", "voice", "api", "dynamodb")
        wait_ready()
        reconnect = client.post(
            "/v1/sessions",
            json={
                "mode": "personal",
                "microphoneConsent": True,
                "conversationId": grant["conversationId"],
            },
        ).json()
        asyncio.run(voice(reconnect))
        assert (
            reconnect["conversationId"] == grant["conversationId"]
            and reconnect["runtimeSessionId"] != grant["runtimeSessionId"]
        )
        checks["restartAndReconnectPreserveConversation"] = True
        checks["disconnectDoesNotCancelTask"] = (
            rpc("tools/call", {"name": "get_task_status", "arguments": {"taskId": tid}})["status"]
            == "READY"
        )
        compose("start", *stopped)
        for _ in range(45):
            current = client.get(f"/v1/goals/{tid}").json()
            if current["status"] in {"SUCCEEDED", "NEEDS_ATTENTION", "FAILED"}:
                break
            time.sleep(1)
        assert current["status"] == "SUCCEEDED", current["status"]
        checks["taskContinuesAfterVoiceCloses"] = True
        day = datetime.now(ZoneInfo("Europe/Paris")).date().isoformat()
        for language, text in (
            ("fr", "Petit déjeuner sucré synthétique"),
            ("en", "Synthetic sweet breakfast"),
        ):
            response = client.post(
                "/v1/memories",
                json={"kind": "exchange", "text": text},
                headers={"Idempotency-Key": uuid4().hex},
            )
            assert response.status_code == 201
            recalled = rpc("tools/call", {"name": "recall_memories", "arguments": {"day": day}})
            assert any(item["text"] == text for item in recalled["items"])
            checks[f"canonicalRecall{language.upper()}"] = True
        for _ in range(15):
            if catchup_contains(tid):
                break
            time.sleep(1)
        assert catchup_contains(tid)
        checks["durableCatchupAfterMissingSignals"] = True
        with ThreadPoolExecutor(max_workers=4) as pool:
            pages = list(
                pool.map(lambda _: client.get("/v1/activity/catchup").status_code, range(12))
            )
        assert all(status == 200 for status in pages)
        checks["boundedFourClientReadBurst"] = True
        for _ in range(10):
            rpc("tools/call", {"name": "get_task_status", "arguments": {"taskId": tid}})
        ordered = sorted(measurements)
        report = {
            "schemaVersion": "1.0",
            "result": "PASS",
            "scope": "local-docker-synthetic-transcripts-simulated-planning-and-commerce",
            "checks": checks,
            "observedLatencyMs": {
                "samples": len(ordered),
                "p50": round(ordered[len(ordered) // 2], 2),
                "p95": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))], 2),
                "scope": "mixed MCP roundtrip and synthetic session readiness; localhost; not speech latency",
            },
            "voiceModelCalls": 0,
            "observedAwsCost": None,
            "awsQualified": False,
            "realSpeechQualified": False,
        }
        (ROOT / "artifacts/stage4-recovery.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report))
    finally:
        compose("start", *stopped)
        client.close()


if __name__ == "__main__":
    main()
