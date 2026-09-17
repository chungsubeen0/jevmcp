import os

import pytest

from jev_mcp.config import load_config
from jev_mcp.models import JudgmentQuestion
from jev_mcp.providers.typesafe import TypeSafeProvider

pytestmark = [
    pytest.mark.live,
    pytest.mark.typesafe,
    pytest.mark.skipif(os.environ.get("JEV_MCP_LIVE") != "1", reason="set JEV_MCP_LIVE=1"),
    pytest.mark.skipif(not os.environ.get("TYPESAFE_API_KEY"), reason="TYPESAFE_API_KEY required"),
]


async def test_live_noul_batch_and_bounds():
    provider = TypeSafeProvider(load_config())
    try:
        result = await provider.evaluate(
            {"failure": "guest_identity expected UUID but received null", "file": "stripe.ts"},
            [
                JudgmentQuestion(id="related", question="Does the supplied evidence mention a null identity?"),
                JudgmentQuestion(id="css", question="Does the supplied evidence mention CSS padding?"),
            ],
        )
    finally:
        await provider.close()
    assert set(result.answers) == {"related", "css"}
    for value in result.answers.values():
        assert 0.0 <= value <= 1.0
    assert result.provider == "typesafe"
    assert result.model
