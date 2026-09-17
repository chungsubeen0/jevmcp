from pathlib import Path

import pytest
from pydantic import ValidationError

from jev_mcp.config import AppConfig, load_config
from jev_mcp.errors import ErrorCode, JevError
from jev_mcp.providers.base import build_provider
from jev_mcp.providers.mock import MockProvider
from jev_mcp.providers.typesafe import TypeSafeProvider, assert_safe_base_url
from jev_mcp.tools._common import engine_profile
from jev_mcp.tools.compare_attempts import run_compare_attempts


def test_project_yaml_cannot_set_secrets_or_host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("TYPESAFE_BASE_URL", raising=False)
    monkeypatch.delenv("JEV_MCP_CONFIG", raising=False)
    (tmp_path / "jev-mcp.yaml").write_text(
        """
provider:
  api_key: stolen
  base_url: https://evil.example
  model: jev-latest
telemetry:
  store_content: true
""",
        encoding="utf-8",
    )
    config = load_config(cwd=tmp_path)
    assert config.provider.api_key is None
    assert config.provider.base_url == "https://api.typesafe.ai"
    assert config.telemetry.store_content is False


def test_env_still_supplies_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("TYPESAFE_API_KEY", "from-env")
    config = load_config(cwd=tmp_path)
    assert config.provider.api_key == "from-env"


def test_timeout_and_retries_capped():
    with pytest.raises(ValidationError):
        AppConfig.model_validate({"provider": {"timeout_seconds": 0.5}})
    with pytest.raises(ValidationError):
        AppConfig.model_validate({"provider": {"max_retries": 99}})
    ok = AppConfig.model_validate({"provider": {"timeout_seconds": 30, "max_retries": 1}})
    assert ok.provider.max_retries == 1


def test_shadow_defaults_on():
    assert AppConfig().server.shadow_mode is True


def test_base_url_must_be_https_allowlisted():
    with pytest.raises(JevError) as exc:
        assert_safe_base_url("http://api.typesafe.ai")
    assert exc.value.code == ErrorCode.PROVIDER_UNAVAILABLE
    with pytest.raises(JevError):
        assert_safe_base_url("https://evil.example")
    assert_safe_base_url("https://api.typesafe.ai")


def test_fault_ignored_without_allow(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JEV_MCP_TEST_FAULT", "unavailable")
    monkeypatch.delenv("JEV_MCP_ALLOW_FAULTS", raising=False)
    provider = build_provider(AppConfig.model_validate({"provider": {"name": "mock"}}))
    assert isinstance(provider, MockProvider)


def test_fault_allowed_when_opted_in(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JEV_MCP_TEST_FAULT", "unavailable")
    monkeypatch.setenv("JEV_MCP_ALLOW_FAULTS", "1")
    provider = build_provider(AppConfig.model_validate({"provider": {"name": "mock"}}))
    assert provider.name == "fault"


async def test_client_mode_does_not_change_profile(app_config):
    engine = __import__("jev_mcp.engine", fromlist=["Engine"]).Engine.create(
        app_config, provider=MockProvider(answers={"same_failure": 0.2})
    )
    from jev_mcp.models import ClientMeta

    assert engine_profile(engine, ClientMeta(mode="autonomous")).name == engine.profile.name
    result = await run_compare_attempts(
        engine,
        task_goal="x",
        previous_attempt={"approach": "a", "failure": "f"},
        current_attempt={"approach": "b", "failure": "g"},
        client={"name": "codex", "mode": "autonomous"},
    )
    assert result["control_signal"] in {"CONTINUE", "REASSESS", "ESCALATE"}


async def test_typesafe_rejects_evil_host_before_request(tmp_path: Path):
    from jev_mcp.models import JudgmentQuestion

    config = AppConfig.model_validate(
        {
            "provider": {
                "name": "typesafe",
                "api_key": "test-key",
                "base_url": "https://evil.example",
            },
            "data_dir": str(tmp_path),
        }
    )
    provider = TypeSafeProvider(config)
    with pytest.raises(JevError) as exc:
        await provider.evaluate({"a": 1}, [JudgmentQuestion(id="Q1", question="X?")])
    assert exc.value.code == ErrorCode.PROVIDER_UNAVAILABLE
    assert "not allowed" in exc.value.message
