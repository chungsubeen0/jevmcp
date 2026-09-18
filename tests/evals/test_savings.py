from evals.savings import compact_payload, measure_case, summarize


def test_config_a_never_counts_avoided_context():
    rows = [
        {
            "tool": "jev_triage_failure",
            "evidence_chars": 1000,
            "context_avoided_chars": 700,
            "stuck_loops_detected": 1,
            "candidates_deprioritized": 2,
            "requirements_isolated": 1,
        }
    ]
    summary = summarize(rows, tools=[], label="A_frontier_only")
    assert summary["jev_calls"] == 0
    assert summary["context_avoided_chars"] == 0
    assert summary["context_avoided_tokens_estimate"] == 0


def test_compact_payload_drops_meta_and_raw_evidence():
    compact = compact_payload(
        {
            "signals": {"related_to_current_change": 0.9},
            "classification": {"relationship": "LIKELY_RELATED"},
            "meta": {"provider": "mock"},
            "advisory": "shadow",
        }
    )
    assert "meta" not in compact
    assert compact["signals"]["related_to_current_change"] == 0.9


def test_measure_case_avoids_only_the_delta():
    case = {"id": "x", "tool": "jev_judge", "source": "benchmark", "input": {"state": "abcd" * 50}}
    result = {"answers": {"Q1": 0.9}}
    measured = measure_case(case, result)
    assert measured["context_avoided_chars"] == measured["evidence_chars"] - measured["compact_chars"]
    assert measured["context_avoided_chars"] > 0
