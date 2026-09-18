from pathlib import Path

import pytest

from jev_mcp.config import AppConfig, load_config
from jev_mcp.http_auth import HttpBindError, assert_http_ready, bearer_matches


def test_loopback_requires_token():
    config = AppConfig.model_validate({"server": {"transport": "streamable-http"}})
    with pytest.raises(HttpBindError):
        assert_http_ready(config)


def test_loopback_ok_with_token():
    config = AppConfig.model_validate(
        {"server": {"http": {"host": "127.0.0.1", "token": "abc"}}}
    )
    assert_http_ready(config)


def test_anon_only_on_loopback():
    config = AppConfig.model_validate(
        {"server": {"http": {"host": "0.0.0.0", "allow_anon": True, "bind_all": True}}}
    )
    with pytest.raises(HttpBindError):
        assert_http_ready(config)


def test_bind_all_requires_token():
    config = AppConfig.model_validate(
        {"server": {"http": {"host": "0.0.0.0", "bind_all": True}}}
    )
    with pytest.raises(HttpBindError):
        assert_http_ready(config)
    ok = AppConfig.model_validate(
        {"server": {"http": {"host": "0.0.0.0", "bind_all": True, "token": "abc"}}}
    )
    assert_http_ready(ok)


def test_non_loopback_without_bind_all_refused():
    config = AppConfig.model_validate(
        {"server": {"http": {"host": "0.0.0.0", "token": "abc"}}}
    )
    with pytest.raises(HttpBindError):
        assert_http_ready(config)


def test_project_yaml_cannot_set_http_bind(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("JEV_MCP_HTTP_HOST", raising=False)
    monkeypatch.delenv("JEV_MCP_HTTP_TOKEN", raising=False)
    monkeypatch.delenv("JEV_MCP_HTTP_BIND_ALL", raising=False)
    monkeypatch.delenv("JEV_MCP_CONFIG", raising=False)
    (tmp_path / "jev-mcp.yaml").write_text(
        """
server:
  transport: streamable-http
  http:
    host: 0.0.0.0
    bind_all: true
    token: stolen-http-token
    allow_anon: true
""",
        encoding="utf-8",
    )
    config = load_config(cwd=tmp_path)
    assert config.server.transport == "stdio"
    assert config.server.http.host == "127.0.0.1"
    assert config.server.http.token is None
    assert config.server.http.bind_all is False
    assert config.server.http.allow_anon is False


def test_env_supplies_http_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("JEV_MCP_HTTP_TOKEN", "from-env-http")
    monkeypatch.setenv("JEV_MCP_TRANSPORT", "streamable-http")
    config = load_config(cwd=tmp_path)
    assert config.server.transport == "streamable-http"
    assert config.server.http.token == "from-env-http"


def test_yaml_token_stripped_from_user_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("JEV_MCP_HTTP_TOKEN", raising=False)
    monkeypatch.delenv("JEV_MCP_CONFIG", raising=False)
    cfg = tmp_path / "xdg" / "jev-mcp" / "config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("server:\n  http:\n    token: yaml-token\n    bind_all: true\n", encoding="utf-8")
    config = load_config(cwd=tmp_path)
    assert config.server.http.token is None
    assert config.server.http.bind_all is False


def test_bearer_compare():
    assert bearer_matches("Bearer secret", "secret")
    assert not bearer_matches("Bearer other", "secret")
    assert not bearer_matches("Basic secret", "secret")
    assert not bearer_matches(None, "secret")
