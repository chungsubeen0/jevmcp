from pathlib import Path

import pytest
from evals.generate import main as generate_main
from evals.metrics import recall_at_k
from evals.runner import load_cases, run_suite

GOLDEN = Path(__file__).resolve().parents[2] / "evals" / "golden"


@pytest.fixture(scope="module", autouse=True)
def golden_files():
    if not any(GOLDEN.glob("*.jsonl")):
        generate_main()


async def test_golden_software_suite(tmp_path):
    cases = load_cases()
    assert len(cases) >= 300
    summary = await run_suite(cases, live=False, data_dir=tmp_path)
    assert summary["directional_accuracy"] == 1.0
    assert summary["critical_recall_at_10"] >= 0.98
    assert summary["missed_requirement_rate"] == 0


def test_recall_prefers_not_missing_critical():
    ranked = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
    assert recall_at_k(ranked, ["a", "j"], 10) == 1.0
    assert recall_at_k(ranked, ["missing"], 10) == 0.0
