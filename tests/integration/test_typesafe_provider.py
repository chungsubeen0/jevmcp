import json

import httpx

from jev_mcp.config import AppConfig
from jev_mcp.models import JudgmentQuestion
from jev_mcp.providers.typesafe import TypeSafeProvider


def _config(tmp_path) -> AppConfig:
    return AppConfig.model_validate(
        {
            "provider": {
                "name": "typesafe",
                "api_key": "test-key",
                "base_url": "https://api.typesafe.ai",
                "model": "jev-latest",
                "timeout_seconds": 5,
                "max_retries": 1,
            },
            "data_dir": str(tmp_path),
        }
    )


async def test_typesafe_parses_noul(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["model"] == "jev-latest"
        assert body["questions"]["Q1"]["type"] == "noul"
        return httpx.Response(
            200,
            json={
                "model": "jev-latest",
                "answers": {"Q1": {"type": "noul", "noul": 0.87}},
                "usage": {"input_tokens": 120, "output_tokens": 4},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = TypeSafeProvider(_config(tmp_path), client=client)
    result = await provider.evaluate(
        {"state": "hello"},
        [JudgmentQuestion(id="Q1", question="Does evidence suggest X?")],
    )
    assert result.answers["Q1"] == 0.87
    assert result.input_units == 120
    await provider.close()


async def test_typesafe_clamps_probability(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"model": "jev-latest", "answers": {"Q1": {"type": "noul", "noul": 1.4}}},
        )

    provider = TypeSafeProvider(
        _config(tmp_path),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = await provider.evaluate(
        {"state": "hello"},
        [JudgmentQuestion(id="Q1", question="Does evidence suggest X?")],
    )
    assert result.answers["Q1"] == 1.0
    await provider.close()
