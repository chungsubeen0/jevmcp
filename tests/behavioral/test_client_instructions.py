from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CODEX = (REPO / "integrations/codex/AGENTS.example.md").read_text(encoding="utf-8")
CLAUDE = (REPO / "integrations/claude-code/CLAUDE.example.md").read_text(encoding="utf-8")


def test_scenario_a_typo_not_forced():
    assert "trivial" in CLAUDE.lower() or "deterministic" in CLAUDE.lower()
    assert "do not call jev for trivial" in CLAUDE.lower() or "immediately obvious" in CLAUDE.lower()


def test_scenario_b_nonobvious_failure_uses_triage():
    assert "jev_triage_failure" in CODEX
    assert "before" in CODEX.lower()


def test_scenario_c_repeated_attempts_use_compare():
    assert "jev_compare_attempts" in CODEX
    assert "two materially unsuccessful" in CODEX.lower() or "repeated" in CODEX.lower()


def test_scenario_d_completion_for_large_tasks():
    assert "jev_check_completion" in CODEX
    assert "requirements" in CODEX.lower()


def test_claude_is_less_aggressive_than_codex():
    assert "selectively" in CLAUDE.lower()
    assert "autonomous" not in CLAUDE.lower() or "interactive" in CLAUDE.lower()
