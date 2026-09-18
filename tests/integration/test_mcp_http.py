from __future__ import annotations

import asyncio

import httpx
import pytest
from tests.helpers.mcp_http import DEFAULT_TOKEN, http_server, http_session, parse_http_tool
from tests.integration.test_mcp_protocol import TRIAGE


async def _request(method: str, url: str, **kwargs):
    async with httpx.AsyncClient(timeout=2.0) as client:
        return await client.request(method, url, **kwargs)


@pytest.mark.asyncio
async def test_http_health_and_triage(tmp_path):
    async with http_server(tmp_path) as base:
        health = await _request("GET", f"{base}/health")
        assert health.status_code == 200
        body = health.json()
        assert body["ok"] is True
        assert body["provider"] == "mock"
        assert "api_key" not in body
        assert DEFAULT_TOKEN not in health.text

        async with http_session(base, DEFAULT_TOKEN) as session:
            result = parse_http_tool(await session.call_tool("jev_triage_failure", TRIAGE))
        assert "signals" in result
        assert "classification" in result
        assert "error" not in result


@pytest.mark.asyncio
async def test_http_rejects_missing_and_wrong_token(tmp_path):
    async with http_server(tmp_path) as base:
        missing = await _request("POST", f"{base}/mcp", json={})
        assert missing.status_code == 401
        assert DEFAULT_TOKEN not in missing.text
        assert "Bearer" in missing.headers.get("www-authenticate", "")

        wrong = await _request(
            "POST",
            f"{base}/mcp",
            json={},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert wrong.status_code == 401
        assert "wrong-token" not in wrong.text
        assert DEFAULT_TOKEN not in wrong.text


@pytest.mark.asyncio
async def test_http_dns_rebind_host_rejected(tmp_path):
    async with http_server(tmp_path) as base:
        response = await _request(
            "POST",
            f"{base}/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            headers={"Authorization": f"Bearer {DEFAULT_TOKEN}", "Host": "evil.example"},
        )
        assert response.status_code in {400, 403, 421}
        assert DEFAULT_TOKEN not in response.text


@pytest.mark.asyncio
async def test_http_concurrent_clients(tmp_path):
    async with http_server(tmp_path) as base:

        async def one() -> dict:
            async with http_session(base, DEFAULT_TOKEN) as session:
                return parse_http_tool(await session.call_tool("jev_triage_failure", TRIAGE))

        first, second = await asyncio.gather(one(), one())
    assert "signals" in first and "signals" in second


@pytest.mark.asyncio
async def test_http_listen_does_not_call_typesafe(tmp_path, monkeypatch: pytest.MonkeyPatch):
    called = False

    async def boom(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("TypeSafe must not be contacted because HTTP listened")

    monkeypatch.setattr("jev_mcp.providers.typesafe.TypeSafeProvider.evaluate", boom)
    async with http_server(tmp_path) as base:
        health = await _request("GET", f"{base}/health")
        assert health.status_code == 200
    assert called is False
