"""One immutable ARM64 image serves either configured AgentCore protocol."""

import os

import uvicorn

if __name__ == "__main__":
    module = os.environ.get("KOYORI_RUNTIME_MODULE")
    allowed = {
        "koyori.voice:create_voice_app": 8080,
        "koyori.mcp_server:create_internal_app": 8000,
    }
    if module not in allowed or int(os.environ.get("KOYORI_RUNTIME_PORT", "0")) != allowed[module]:
        raise ValueError("Select an admitted runtime module and port")
    uvicorn.run(
        module,
        factory=True,
        host="0.0.0.0",
        port=allowed[module],
        access_log=False,
        ws_max_size=8192,
        ws_max_queue=4,
    )
