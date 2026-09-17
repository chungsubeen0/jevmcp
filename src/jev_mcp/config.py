"""Configuration loading. Precedence: CLI/env > project > user > defaults."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from jev_mcp.models import ProbabilityBands, StuckThresholds

ProfileName = Literal["autonomous", "interactive", "custom"]
ProviderName = Literal["typesafe", "mock"]


class ServerConfig(BaseModel):
    log_level: str = "INFO"
    shadow_mode: bool = True


class ProviderConfig(BaseModel):
    name: ProviderName = "typesafe"
    model: str = "jev-latest"
    base_url: str = "https://api.typesafe.ai"
    api_key: str | None = None
    timeout_seconds: float = 30.0
    max_retries: int = 1

    @field_validator("timeout_seconds")
    @classmethod
    def _bounded_timeout(cls, value: float) -> float:
        if not 1.0 <= value <= 120.0:
            raise ValueError("timeout_seconds must be between 1 and 120")
        return value

    @field_validator("max_retries")
    @classmethod
    def _bounded_retries(cls, value: int) -> int:
        if not 0 <= value <= 2:
            raise ValueError("max_retries must be between 0 and 2")
        return value


class ProfileConfig(BaseModel):
    default: ProfileName = "interactive"


class LimitsConfig(BaseModel):
    max_state_chars: int = 100_000
    max_question_count: int = 100
    max_question_chars: int = 2_000
    max_candidates: int = 25
    max_candidate_chars: int = 8_000
    max_findings: int = 50
    max_requirements: int = 50


class ThresholdsConfig(BaseModel):
    default: ProbabilityBands = Field(default_factory=ProbabilityBands)
    stuck: StuckThresholds = Field(default_factory=StuckThresholds)


class CacheConfig(BaseModel):
    enabled: bool = True
    backend: Literal["sqlite"] = "sqlite"
    ttl_seconds: int = 3600
    max_entries: int = 10_000
    path: str | None = None


class TelemetryConfig(BaseModel):
    enabled: bool = True
    store_content: bool = False
    store_hashes: bool = True
    local_only: bool = True
    path: str | None = None


class CostConfig(BaseModel):
    jev_input_per_million: float | None = None


class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    profile: ProfileConfig = Field(default_factory=ProfileConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)
    cost: CostConfig = Field(default_factory=CostConfig)
    data_dir: str | None = None

    def resolve_data_dir(self) -> Path:
        if self.data_dir:
            return Path(self.data_dir).expanduser()
        env = os.environ.get("JEV_MCP_DATA_DIR")
        if env:
            return Path(env).expanduser()
        return Path.home() / ".local" / "share" / "jev-mcp"

    def cache_path(self) -> Path:
        if self.cache.path:
            return Path(self.cache.path).expanduser()
        return self.resolve_data_dir() / "cache.sqlite"

    def telemetry_path(self) -> Path:
        if self.telemetry.path:
            return Path(self.telemetry.path).expanduser()
        return self.resolve_data_dir() / "telemetry.sqlite"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"config file must be a mapping: {path}")
    return loaded


def _strip_secrets(data: dict[str, Any]) -> dict[str, Any]:
    """YAML must never supply credentials or provider hosts."""
    provider = data.get("provider")
    if isinstance(provider, dict):
        provider.pop("api_key", None)
        provider.pop("base_url", None)
    return data


def _strip_project_privileges(data: dict[str, Any]) -> dict[str, Any]:
    telemetry = data.get("telemetry")
    if isinstance(telemetry, dict):
        telemetry.pop("store_content", None)
    return data


def _project_config_path(cwd: Path | None = None) -> Path | None:
    root = cwd or Path.cwd()
    for name in ("jev-mcp.yaml", "jev-mcp.yml", "config.yaml"):
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None


def _user_config_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "jev-mcp" / "config.yaml"


def _env_overrides() -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    provider: dict[str, Any] = {}
    server: dict[str, Any] = {}
    profile: dict[str, Any] = {}

    if key := os.environ.get("TYPESAFE_API_KEY"):
        provider["api_key"] = key
    if url := os.environ.get("TYPESAFE_BASE_URL"):
        provider["base_url"] = url
    if model := os.environ.get("TYPESAFE_MODEL") or os.environ.get("TYPESAFE_DEFAULT_MODEL"):
        provider["model"] = model
    if timeout := os.environ.get("TYPESAFE_TIMEOUT_SECONDS"):
        provider["timeout_seconds"] = float(timeout)
    if name := os.environ.get("JEV_MCP_PROVIDER"):
        provider["name"] = name
    if provider:
        overrides["provider"] = provider

    if level := os.environ.get("JEV_MCP_LOG_LEVEL"):
        server["log_level"] = level
    shadow = os.environ.get("JEV_MCP_SHADOW_MODE")
    if shadow is not None:
        server["shadow_mode"] = shadow.strip().lower() in {"1", "true", "yes", "on"}
    if server:
        overrides["server"] = server

    if default_profile := os.environ.get("JEV_MCP_PROFILE"):
        profile["default"] = default_profile
        overrides["profile"] = profile

    if data_dir := os.environ.get("JEV_MCP_DATA_DIR"):
        overrides["data_dir"] = data_dir
    return overrides


def load_config(
    *,
    config_path: str | Path | None = None,
    cli_overrides: dict[str, Any] | None = None,
    cwd: Path | None = None,
) -> AppConfig:
    data: dict[str, Any] = {}
    user = _strip_secrets(_read_yaml(_user_config_path()))
    data = _deep_merge(data, user)

    project = _project_config_path(cwd)
    if project:
        data = _deep_merge(data, _strip_project_privileges(_strip_secrets(_read_yaml(project))))

    explicit = config_path or os.environ.get("JEV_MCP_CONFIG")
    if explicit:
        data = _deep_merge(data, _strip_project_privileges(_strip_secrets(_read_yaml(Path(explicit).expanduser()))))

    data = _deep_merge(data, _env_overrides())
    if cli_overrides:
        data = _deep_merge(data, cli_overrides)
    return AppConfig.model_validate(data)
