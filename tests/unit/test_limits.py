from jev_mcp.config import AppConfig
from jev_mcp.engine import Engine
from jev_mcp.normalization.text import normalize_text
from jev_mcp.providers.mock import MockProvider
from jev_mcp.tools.judge import run_judge
from jev_mcp.util.limits import apply_char_limit


def test_truncation_preserves_ends():
    text = "HEAD" + ("x" * 1000) + "TAIL"
    clipped, report = apply_char_limit(text, 80, label="input")
    assert report.truncated is True
    assert clipped.startswith("HEAD")
    assert "TAIL" in clipped
    assert "truncated" in clipped.lower() or "truncated" in report.warnings[0]


def test_ansi_and_progress_stripped():
    raw = "hello\x1b[31mred\x1b[0m\nProgress 10%|\nProgress 20%|\nProgress 30%|\nerror"
    cleaned = normalize_text(raw)
    assert "\x1b" not in cleaned
    assert cleaned.count("Progress") == 1


async def test_judge_warns_on_truncation(tmp_path):
    config = AppConfig.model_validate(
        {
            "provider": {"name": "mock"},
            "data_dir": str(tmp_path),
            "limits": {"max_state_chars": 40},
        }
    )
    engine = Engine.create(config, provider=MockProvider(default=0.5))
    result = await run_judge(
        engine,
        state={"blob": "z" * 5000},
        questions=[{"id": "Q1", "question": "Does the supplied evidence suggest overflow?"}],
    )
    assert result["warnings"]
    assert any("truncated" in warning.lower() for warning in result["warnings"])
