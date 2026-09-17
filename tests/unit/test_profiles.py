from jev_mcp.config import AppConfig
from jev_mcp.models import ClientMeta
from jev_mcp.policy.profiles import resolve_profile
from jev_mcp.tools._common import engine_profile


def test_profiles_do_not_change_truth_values():
    autonomous = resolve_profile(AppConfig(profile={"default": "autonomous"}))
    interactive = resolve_profile(AppConfig(profile={"default": "interactive"}))
    assert autonomous.failure_triage == "aggressive"
    assert interactive.failure_triage == "moderate"
    assert autonomous.context_ranking != interactive.context_ranking
    assert autonomous.high_tier_useful_now < interactive.high_tier_useful_now


def test_client_cannot_override_server_profile(tmp_path):
    config = AppConfig.model_validate(
        {"profile": {"default": "interactive"}, "data_dir": str(tmp_path), "provider": {"name": "mock"}}
    )
    from jev_mcp.engine import Engine
    from jev_mcp.providers.mock import MockProvider

    engine = Engine.create(config, provider=MockProvider())
    assert engine_profile(engine, ClientMeta(mode="autonomous")).name == "interactive"
