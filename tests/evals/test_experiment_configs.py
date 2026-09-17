from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parents[2] / "evals" / "experiments" / "configs.yaml"


def test_four_configurations_exist():
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert data["A_frontier_only"]["tools"] == []
    assert data["B_triage"]["tools"] == ["jev_triage_failure"]
    assert "jev_compare_attempts" in data["C_triage_and_stuck"]["tools"]
    assert len(data["D_all"]["tools"]) == 7
    assert data["primary_metric"] == "frontier_inference_cost_per_successful_task"
