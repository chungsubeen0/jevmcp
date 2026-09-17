from __future__ import annotations

from pathlib import Path

import pytest

from jev_mcp.config import AppConfig
from jev_mcp.engine import Engine
from jev_mcp.providers.mock import MockProvider


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    return tmp_path / "data"


@pytest.fixture
def app_config(tmp_data_dir: Path) -> AppConfig:
    return AppConfig.model_validate(
        {
            "provider": {"name": "mock", "model": "mock-jev"},
            "data_dir": str(tmp_data_dir),
            "server": {"shadow_mode": False},
            "telemetry": {"enabled": True, "store_content": False, "store_hashes": True},
            "cache": {"enabled": True, "ttl_seconds": 3600, "max_entries": 100},
        }
    )


@pytest.fixture
def mock_provider() -> MockProvider:
    return MockProvider(default=0.5)


@pytest.fixture
def engine(app_config: AppConfig, mock_provider: MockProvider) -> Engine:
    return Engine.create(app_config, provider=mock_provider)
