from jev_mcp.engine import Engine
from jev_mcp.providers.mock import MockJudgmentProvider
from jev_mcp.tools.assess_risk import run_assess_risk


async def test_assess_risk_auth_payment(app_config):
    provider = MockJudgmentProvider(
        answers={
            "security_sensitive": 0.91,
            "authentication_sensitive": 0.96,
            "authorization_sensitive": 0.80,
            "data_integrity_sensitive": 0.40,
            "schema_sensitive": 0.10,
            "public_api_sensitive": 0.20,
            "architecture_sensitive": 0.21,
            "payment_sensitive": 0.84,
            "broad_regression_risk": 0.40,
        }
    )
    engine = Engine.create(app_config, provider=provider)
    result = await run_assess_risk(
        engine,
        task_goal="checkout identity",
        changed_files=["src/auth.ts"],
        diff_summary="trust client user id",
    )
    assert result["signals"]["authentication_sensitive"] == 0.96
    assert result["further_frontier_review_warranted"] is True
    assert "not a security conclusion" in result["note"].lower()
