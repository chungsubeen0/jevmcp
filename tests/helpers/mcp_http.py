from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from tests.helpers.mcp_stdio import parse_tool_result

from jev_mcp.config import AppConfig
from jev_mcp.server import build_http_app, init_engine

DEFAULT_TOKEN = "jev-http-test-token"


@asynccontextmanager
async def http_server(
    tmp_path: Path,
    *,
    token: str | None = DEFAULT_TOKEN,
    require_token: bool = True,
    allow_anon: bool = False,
) -> AsyncIterator[str]:
    config = AppConfig.model_validate(
        {
            "provider": {"name": "mock", "model": "mock-jev"},
            "data_dir": str(tmp_path),
            "server": {
                "transport": "streamable-http",
                "shadow_mode": True,
                "log_level": "WARNING",
                "http": {
                    "host": "127.0.0.1",
                    "port": 8765,
                    "path": "/mcp",
                    "token": token,
                    "require_token": require_token,
                    "allow_anon": allow_anon,
                },
            },
        }
    )
    init_engine(config)
    app = build_http_app(config)

    import uvicorn

    uv = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(uv)
    task = asyncio.create_task(server.serve())
    try:
        for _ in range(400):
            if server.started:
                break
            await asyncio.sleep(0.01)
        else:
            raise RuntimeError("HTTP server did not start")
        port = server.servers[0].sockets[0].getsockname()[1]
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await task


@asynccontextmanager
async def http_session(base_url: str, token: str | None) -> AsyncIterator[ClientSession]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    client = httpx.AsyncClient(headers=headers)
    try:
        async with streamable_http_client(f"{base_url}/mcp", http_client=client) as streams:
            read, write = streams[:2]
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
    finally:
        await client.aclose()


def parse_http_tool(result: Any) -> dict[str, Any]:
    return parse_tool_result(result)
