"""HTTP/MCP recipe on the reconstructed runtime; synthetic declarations and acceptance."""

import json
import time
from uuid import uuid4

import httpx
from verify_local import BASE, ROOT, compose, wait_ready
from verify_stage2 import proof

from koyori.stage2_contracts import MemoryWrite
from koyori.stage4_contracts import MemoryErase


def main():
    wait_ready()
    access = compose(
        "run", "--rm", "--no-deps", "demo", "python", "-m", "koyori.demo", "token", "alex"
    ).strip()
    mcp_access = compose(
        "run", "--rm", "--no-deps", "demo", "python", "-m", "koyori.demo", "token", "alex", "--mcp"
    ).strip()
    checks = {}
    with httpx.Client(
        base_url=BASE, timeout=15, headers={"Authorization": f"Bearer {access}"}
    ) as client:

        def write(path, body, version=None, grant=None, method="POST"):
            headers = {"Idempotency-Key": uuid4().hex}
            if version is not None:
                headers["If-Match"] = f'"{version}"'
            if grant:
                headers["X-Step-Up-Grant"] = grant
            response = client.request(method, path, json=body, headers=headers)
            assert response.status_code in {200, 201, 202}, (path, response.status_code)
            return response.json()

        h = write("/v1/households", {"name": "Synthetic memory qualification"})["id"]
        client.headers["X-Household-Id"] = h
        old = write(
            "/v1/memories",
            MemoryWrite(
                kind="preference",
                key="dessert",
                text="Crème moins sucrée",
                occurredAt=int(time.time()) - 60 * 86400,
            ).model_dump(),
        )
        archive = write(
            "/v1/memories",
            MemoryWrite(
                kind="exchange", text="Une crème au CAFÉ", occurredAt=int(time.time()) - 30 * 86400
            ).model_dump(),
        )
        declaration = write(
            "/v1/memories",
            MemoryWrite(
                kind="exchange", text="Je préfère le chocolat au petit déjeuner"
            ).model_dump(),
        )
        core = client.post("/v1/context", json={"day": "yesterday", "includeCore": True}).json()
        assert core["items"] == [] and old["id"] in {i["id"] for i in core["coreItems"]}
        checks["coreSeparateFromCivilDay"] = True
        for _ in range(60):
            page = client.get("/v1/learning").json()
            proposed = next(
                (p for p in page["items"] if p["source"].get("id") == declaration["id"]), None
            )
            if proposed:
                break
            time.sleep(1)
        assert proposed and proposed["origin"] == "automatic" and proposed["mode"] == "simulated"
        before = client.post(
            "/v1/context", json={"key": "breakfast_drink", "includeCore": True}
        ).json()
        assert before["items"] == before["coreItems"] == []
        accepted = write(
            f"/v1/learning/{proposed['id']}/decisions", {"decision": "accept"}, proposed["rev"]
        )
        after = client.post(
            "/v1/context", json={"key": "breakfast_drink", "includeCore": True}
        ).json()
        assert accepted["memoryId"] in {i["id"] for i in after["coreItems"]}
        checks["simulatedLearningRequiresAcceptance"] = True
        for _ in range(60):
            found = client.post("/v1/memories/search", json={"query": "CREME cafe"}).json()
            if found["items"]:
                break
            time.sleep(1)
        assert [i["id"] for i in found["items"]] == [archive["id"]]
        checks["oldAccentInsensitiveArchive"] = True
        rpc = client.post(
            "/mcp",
            headers={
                "Authorization": f"Bearer {mcp_access}",
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": "2025-11-25",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "search_memories", "arguments": {"query": "creme cafe"}},
            },
        )
        assert rpc.status_code == 200 and not rpc.json()["result"].get("isError"), rpc.status_code
        assert rpc.json()["result"]["structuredContent"]["items"][0]["id"] == archive["id"]
        checks["commonMcpSearchTool"] = True
        write(f"/v1/memories/{archive['id']}", {}, archive["rev"], method="DELETE")
        assert (
            client.post("/v1/memories/search", json={"query": "creme cafe"}).json()["items"] == []
        )
        checks["canonicalErasureHidesPendingIndex"] = True
        body = MemoryErase(confirmation="erase-my-memories").model_dump()
        grant = proof(client, "POST /v1/privacy/memories/erase", body)
        erase = write("/v1/privacy/memories/erase", body, grant=grant)
        for _ in range(60):
            state = client.get(f"/v1/privacy/erasures/{erase['id']}").json()
            if state.get("status") == "COMPLETED":
                break
            time.sleep(1)
        assert state.get("status") == "COMPLETED", state.get("status")
        assert client.get("/v1/learning").json()["items"] == []
        checks["completeErasureIncludesProposals"] = True
    output = ROOT / "artifacts/memory-hermes.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(
        json.dumps({"result": "PASS", "mode": "synthetic-local", "checks": checks}, indent=2) + "\n"
    )
    print(json.dumps({"result": "PASS", "checks": checks}))


if __name__ == "__main__":
    main()
