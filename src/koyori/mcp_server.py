"""Official SDK Streamable HTTP, stateless JSON; trusted authority stays outside model input."""

import json
import logging
from contextvars import ContextVar

import anyio
from mcp import types
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse, Response

from koyori.channel_tools import CONTRACTS, DESCRIPTIONS, ChannelTools
from koyori.errors import Problem
from koyori.sessions import Sessions

PROTOCOL = "2025-11-25"
RESERVED = "koyori/internal-grant"
AUTHORITY = ContextVar("koyori_channel_authority", default=None)


class MCPTransport:
    def __init__(self, domain, tokens=None, *, internal=False, goals=None):
        self.domain, self.tokens, self.internal = domain, tokens, internal
        self.tools = ChannelTools(domain, goals)
        self.server = Server("koyori", version="1.0.0")
        # SDK validation errors may include caller-supplied argument values.
        for name in ("mcp.server", "mcp.shared"):
            logger = logging.getLogger(name)
            logger.handlers = [logging.NullHandler()]
            logger.propagate = False

        @self.server.list_tools()
        async def list_tools():
            return [
                types.Tool(
                    name=name,
                    description=DESCRIPTIONS[name],
                    inputSchema=model.model_json_schema(),
                    annotations=types.ToolAnnotations(
                        readOnlyHint=name.startswith(("get_", "recall_")),
                        destructiveHint=name == "cancel_goal",
                        idempotentHint=True,
                        openWorldHint=False,
                    ),
                )
                for name, model in CONTRACTS.items()
            ]

        @self.server.call_tool(validate_input=False)
        async def call_tool(name, arguments):
            try:
                return await anyio.to_thread.run_sync(
                    self.tools.call, AUTHORITY.get(), name, arguments
                )
            except Problem as exc:
                return types.CallToolResult(
                    isError=True,
                    content=[
                        types.TextContent(
                            type="text",
                            text=json.dumps({"code": exc.code, "retryable": exc.retryable}),
                        )
                    ],
                )
            except Exception:
                return types.CallToolResult(
                    isError=True,
                    content=[
                        types.TextContent(
                            type="text", text='{"code":"DEPENDENCY_UNAVAILABLE","retryable":true}'
                        )
                    ],
                )

    async def handle(self, request):
        response = await self._handle(request)
        # Let the ASGI host frame replies for streaming-capable MCP clients. A local
        # intermediary rewrote Content-Length to chunked without framing the body.
        if "content-length" in response.headers:
            del response.headers["content-length"]
        return response

    async def _handle(self, request):
        resource = self.domain.settings.mcp_resource
        challenge = f'Bearer resource_metadata="{resource.rsplit("/mcp", 1)[0]}/.well-known/oauth-protected-resource/mcp"'
        try:
            origin = request.headers.get("origin")
            if origin and origin not in self.domain.settings.allowed_origins:
                raise Problem(403, "INVALID_ORIGIN", "Origin is not allowed.")
            if request.method != "POST":
                return Response(status_code=405, headers={"Allow": "POST"})
            raw = await request.body()
            if len(raw) > 32768:
                raise Problem(413, "REQUEST_TOO_LARGE", "Request exceeds 32 KiB.")
            try:
                body = json.loads(raw)
                if not isinstance(body, dict):
                    raise ValueError
                if "params" in body and not isinstance(body["params"], dict):
                    raise ValueError
            except (ValueError, TypeError):
                raise Problem(400, "INVALID_REQUEST", "One JSON-RPC object is required.") from None
            version = request.headers.get("mcp-protocol-version")
            if version and version != PROTOCOL:
                raise Problem(400, "UNSUPPORTED_PROTOCOL", "Unsupported MCP protocol version.")
            if (
                body.get("method") == "initialize"
                and body.get("params", {}).get("protocolVersion") != PROTOCOL
            ):
                raise Problem(400, "UNSUPPORTED_PROTOCOL", "Use MCP 2025-11-25.")
            if self.internal:
                secret = body.get("params", {}).get("_meta", {}).get(RESERVED)
                if not isinstance(secret, str) or len(secret) != 43:
                    raise Problem(401, "INVALID_GRANT", "Internal authority is required.")
                Sessions(self.domain).resolve(secret)
            else:
                authorization = request.headers.get("authorization", "")
                if not authorization.startswith("Bearer ") or len(authorization) > 8192:
                    raise Problem(401, "INVALID_TOKEN", "MCP authentication required.")
                actor = self.tokens.verify(authorization[7:], resource=resource)["sub"]
                household = request.headers.get("x-household-id", "")
                ctx = self.domain.context(actor, household)
                secret = Sessions(self.domain).grant(
                    ctx, mode="shared" if ctx.profile["kind"] == "shared" else "personal"
                )
                if self.domain.settings.env != "local":
                    return await anyio.to_thread.run_sync(
                        self.proxy, body, secret, request.headers.get("mcp-session-id")
                    )
            # Replace client authority, including discovery metadata, on every request.
            if isinstance(body.get("params"), dict):
                body["params"]["_meta"] = {RESERVED: secret}
            safe_body = json.dumps(body).encode()
            sent = False

            async def receive():
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": safe_body, "more_body": False}
                return await request.receive()

            messages = []

            async def send(message):
                messages.append(message)

            manager = StreamableHTTPSessionManager(
                self.server,
                json_response=True,
                stateless=True,
                security_settings=TransportSecuritySettings(enable_dns_rebinding_protection=False),
                max_request_body_size=32768,
            )
            binding = AUTHORITY.set(secret)
            try:
                async with manager.run():
                    await manager.handle_request(request.scope, receive, send)
            finally:
                AUTHORITY.reset(binding)
            start = next(m for m in messages if m["type"] == "http.response.start")
            content = b"".join(
                m.get("body", b"") for m in messages if m["type"] == "http.response.body"
            )
            return Response(
                content,
                start["status"],
                headers={k.decode(): v.decode() for k, v in start["headers"]}
                | {"Cache-Control": "no-store"},
            )
        except Problem as exc:
            return JSONResponse(
                {"code": exc.code, "retryable": exc.retryable},
                exc.status,
                headers={"WWW-Authenticate": challenge, "Cache-Control": "no-store"},
            )

    def proxy(self, body, secret, session_id=None):
        arn = self.domain.settings.mcp_runtime_arn
        if not arn:
            raise Problem(503, "MCP_UNCONFIGURED", "MCP runtime is unavailable.")
        body.setdefault("params", {})["_meta"] = {RESERVED: secret}
        result = self.domain.settings.client("bedrock-agentcore").invoke_agent_runtime(
            agentRuntimeArn=arn,
            contentType="application/json",
            accept="application/json",
            mcpProtocolVersion=PROTOCOL,
            payload=json.dumps(body).encode(),
            **({"mcpSessionId": session_id} if session_id else {}),
        )
        data = result["response"].read(65537)
        if len(data) > 65536:
            raise Problem(502, "MCP_RESPONSE_TOO_LARGE", "Runtime response exceeds bounds.")
        headers = {"Cache-Control": "no-store"}
        for field, header in (
            ("mcpSessionId", "Mcp-Session-Id"),
            ("mcpProtocolVersion", "MCP-Protocol-Version"),
        ):
            if result.get(field):
                headers[header] = result[field]
        for header, value in result.get("ResponseMetadata", {}).get("HTTPHeaders", {}).items():
            if header.lower() in {"www-authenticate", "retry-after"}:
                headers[header] = value
        return Response(
            data,
            status_code=result["statusCode"],
            media_type=result.get("contentType", "application/json"),
            headers=headers,
        )


def create_internal_app():
    from fastapi import FastAPI, Request

    from koyori.config import Settings
    from koyori.domain import Domain
    from koyori.security import Cursors
    from koyori.store import DynamoStore

    settings = Settings.from_env()
    domain = Domain(DynamoStore(settings), settings, Cursors(settings.cursor_secret()))
    transport = MCPTransport(domain, internal=True)
    app = FastAPI(docs_url=None, redoc_url=None)

    @app.api_route("/mcp", methods=["GET", "POST", "DELETE"])
    async def endpoint(request: Request):
        return await transport.handle(request)

    return app
