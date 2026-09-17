import jev_mcp.server as server
from jev_mcp.config import AppConfig
from jev_mcp.providers.mock import MockProvider
from jev_mcp.server import init_engine

EXPECTED_TOOLS = {
    "jev_triage_failure",
    "jev_compare_attempts",
    "jev_check_completion",
    "jev_rank_context",
    "jev_classify_findings",
    "jev_assess_risk",
    "jev_judge",
}


def test_all_v1_tools_registered():
    for name in EXPECTED_TOOLS:
        assert hasattr(server, name)


def test_startup_does_not_require_api_key(tmp_path):
    config = AppConfig.model_validate(
        {
            "provider": {"name": "typesafe", "api_key": None},
            "data_dir": str(tmp_path),
        }
    )
    engine = init_engine(config, provider=MockProvider())
    assert engine.provider.name == "mock"
