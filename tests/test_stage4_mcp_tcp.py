"""MCP responses must reach clients through the real HTTP server and middleware."""

import socket
import threading
import time

import httpx
import uvicorn

from koyori.demo import token


def test_mcp_initialize_and_discovery_over_tcp(harness):
    h = harness
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server = uvicorn.Server(
        uvicorn.Config(h.client.app, lifespan="off", log_level="error", timeout_keep_alive=1)
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started, "HTTP server did not start"
        with httpx.Client(
            base_url=f"http://127.0.0.1:{listener.getsockname()[1]}",
            timeout=5,
            headers={
                "Authorization": f"Bearer {token(h.settings, 'alex', mcp=True)}",
                "X-Household-Id": h.h,
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": "2025-11-25",
            },
        ) as client:
            for method, params in (
                (
                    "initialize",
                    {
                        "protocolVersion": "2025-11-25",
                        "capabilities": {},
                        "clientInfo": {"name": "tcp-regression", "version": "1"},
                    },
                ),
                ("tools/list", {}),
            ):
                response = client.post(
                    "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
                )
                assert response.status_code == 200
                assert response.json()["result"]
                assert response.headers["cache-control"] == "no-store"
            refused = client.post("/mcp", json={}, headers={"Authorization": "invalid"})
            assert refused.status_code == 401
            assert refused.json()["code"] == "INVALID_TOKEN"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
        assert not thread.is_alive(), "HTTP server did not stop"
