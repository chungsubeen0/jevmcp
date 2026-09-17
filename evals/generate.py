"""Generate the V1 golden coding-decision corpus. Human-reviewed labels live in the templates."""

from __future__ import annotations

import json
from pathlib import Path

from evals.schema import GoldenCase, Labels

ROOT = Path(__file__).parent / "golden"


def _write(category: str, cases: list[GoldenCase]) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    path = ROOT / f"{category}.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(case.model_dump(), sort_keys=True) + "\n")


def compare_attempts() -> list[GoldenCase]:
    cases: list[GoldenCase] = []
    combos = [
        ("same-same", True, True, False, False, "LIKELY_STUCK", "same error + same strategy"),
        ("same-diff", True, False, True, True, "PROGRESSING", "same error + different strategy"),
        ("diff-same", False, True, True, True, "PROGRESSING", "different error + same strategy"),
        ("diff-diff", False, False, True, True, "PROGRESSING", "different error + different strategy"),
    ]
    stems = [
        ("guest identity", "null user id", "normalize email", "lookup by customer id"),
        ("webhook signature", "invalid signature", "retry verify", "use raw body"),
        ("checkout tax", "NaN tax", "default 0", "use region table"),
        ("session cookie", "cookie missing", "set later", "set on create"),
        ("migration", "connection refused", "retry connect", "run migrate; UNIQUE fail"),
    ]
    idx = 0
    for stem, fail_a, approach_a, approach_b in stems:
        for _key, same_fail, same_strat, new_ev, progress, status, notes in combos:
            idx += 1
            fail_b = fail_a if same_fail else f"{fail_a} then advanced: UNIQUE constraint"
            cases.append(
                GoldenCase(
                    id=f"stuck-{idx:04d}",
                    category="compare_attempts",
                    task=f"Fix {stem}",
                    input={
                        "task_goal": f"Fix {stem}",
                        "previous_attempt": {"approach": approach_a, "failure": fail_a},
                        "current_attempt": {
                            "approach": approach_a if same_strat else approach_b,
                            "failure": fail_b,
                        },
                    },
                    labels=Labels(
                        expected_status=status,
                        expected_band={
                            "same_failure": "HIGH" if same_fail else "LOW",
                            "same_strategy": "HIGH" if same_strat else "LOW",
                            "meaningful_progress": "HIGH" if progress else "LOW",
                            "meaningful_new_evidence": "HIGH" if new_ev else "LOW",
                        },
                        boolean_labels={
                            "same_failure": same_fail,
                            "same_strategy": same_strat,
                            "meaningful_progress": progress,
                            "new_evidence": new_ev,
                        },
                        notes=notes,
                    ),
                    mock_answers={
                        "same_failure": 0.93 if same_fail else 0.12,
                        "same_strategy": 0.91 if same_strat else 0.14,
                        "meaningful_new_evidence": 0.86 if new_ev else 0.11,
                        "meaningful_progress": 0.82 if progress else 0.16,
                        "reconsider_approach": 0.90 if status == "LIKELY_STUCK" else 0.20,
                    },
                )
            )
    # Ambiguous: same subsystem, unclear help
    for i in range(1, 21):
        cases.append(
            GoldenCase(
                id=f"stuck-amb-{i:04d}",
                category="compare_attempts",
                task="Ambiguous retry",
                input={
                    "task_goal": "Fix flaky identity",
                    "previous_attempt": {"approach": "retry lookup", "failure": "timeout then null"},
                    "current_attempt": {"approach": "retry lookup with backoff", "failure": "timeout then null"},
                },
                labels=Labels(
                    expected_status="UNCERTAIN",
                    expected_band={"same_failure": "UNCERTAIN", "meaningful_progress": "UNCERTAIN"},
                    uncertain_expected=True,
                    notes="strategy shifted slightly; evidence insufficient",
                ),
                mock_answers={
                    "same_failure": 0.51,
                    "same_strategy": 0.55,
                    "meaningful_new_evidence": 0.48,
                    "meaningful_progress": 0.47,
                    "reconsider_approach": 0.52,
                },
            )
        )
    return cases


def triage_failure() -> list[GoldenCase]:
    catalog = [
        ("change-causes", "guest webhook", "src/webhooks/stripe.ts", "guest user ID is null", "HIGH", False),
        ("preexisting", "rename button", "src/ui/Button.tsx", "legacy tax fixture fail", "LOW", False),
        ("environment", "css padding", "src/ui/Button.tsx", "PostgreSQL connection timeout", "LOW", False),
        ("flaky", "copy change", "src/ui/Label.tsx", "test timed out after 30s intermittently", "LOW", False),
        ("dependency", "docs typo", "README.md", "npm registry 503", "LOW", False),
        ("unrelated", "comment only", "src/util/fmt.ts", "auth e2e login expired", "LOW", False),
        ("local-defect", "guest webhook", "src/webhooks/stripe.ts", "resolveGuest returns null", "HIGH", False),
        ("cross-cutting", "shared identity", "src/identity/resolve.ts", "orders and webhooks both null", "HIGH", False),
        ("ambiguous", "unknown", "", "AssertionError", "UNCERTAIN", True),
        ("insufficient", "fix checkout", "", "FAIL", "UNCERTAIN", True),
    ]
    cases: list[GoldenCase] = []
    n = 0
    for _repeat in range(8):
        for key, task, path, failure, related, uncertain in catalog:
            n += 1
            high = related == "HIGH"
            cases.append(
                GoldenCase(
                    id=f"triage-{n:04d}",
                    category="triage_failure",
                    task=task,
                    input={
                        "task": {"goal": task, "requirements": []},
                        "current_step": key,
                        "failure": {"command": "pytest", "exit_code": 1, "summary": failure, "output": failure},
                        "changed_files": [path] if path else [],
                        "diff_summary": path or "",
                    },
                    labels=Labels(
                        expected_band={"related_to_current_change": related},
                        uncertain_expected=uncertain,
                        notes=key,
                    ),
                    mock_answers={
                        "related_to_current_change": 0.94 if high else 0.50 if uncertain else 0.08,
                        "likely_localized": 0.88 if high else 0.50 if uncertain else 0.12,
                        "likely_preexisting": 0.06 if high else 0.50 if uncertain else 0.86,
                        "requirement_related": 0.80 if high else 0.45,
                        "same_as_previous_failure": 0.20,
                        "needs_deeper_reasoning": 0.80 if uncertain else 0.25,
                    },
                )
            )
    return cases


def check_completion() -> list[GoldenCase]:
    cases: list[GoldenCase] = []
    for i in range(1, 61):
        cases.append(
            GoldenCase(
                id=f"complete-{i:04d}",
                category="check_completion",
                task="Guest checkout requirements",
                input={
                    "task": {
                        "goal": "Guest checkout",
                        "requirements": [
                            {"id": "R1", "text": "canonical user created"},
                            {"id": "R2", "text": "receipt test exists"},
                            {"id": "R3", "text": "refund path for guest"},
                            {"id": "R4", "text": "audit trail"},
                        ],
                    },
                    "implementation": {"changed_files": ["checkout.ts"], "diff_summary": "guest user + receipt test"},
                    "verification": {"tests": "identity and receipt passed"},
                },
                labels=Labels(
                    expected_status="INCOMPLETE",
                    review_ids=["R3", "R4"],
                    expected_band={"R3::possible_gap": "HIGH", "R4::appears_satisfied": "UNCERTAIN"},
                    notes="R1/R2 clear; R3 subtly absent; R4 insufficient evidence",
                ),
                mock_answers={
                    "R1::appears_satisfied": 0.96,
                    "R1::evidence_present": 0.94,
                    "R1::possible_gap": 0.05,
                    "R2::appears_satisfied": 0.93,
                    "R2::evidence_present": 0.91,
                    "R2::possible_gap": 0.07,
                    "R3::appears_satisfied": 0.22,
                    "R3::evidence_present": 0.18,
                    "R3::possible_gap": 0.86,
                    "R4::appears_satisfied": 0.51,
                    "R4::evidence_present": 0.44,
                    "R4::possible_gap": 0.49,
                    "scope_appropriate": 0.80,
                    "unresolved_requirement": 0.84,
                    "further_review_warranted": 0.80,
                },
            )
        )
    return cases


def rank_context() -> list[GoldenCase]:
    candidates = [
        ("stripe-webhook.ts", "HIGH"),
        ("identity.ts", "HIGH"),
        ("orders.ts", "MEDIUM"),
        ("checkout.ts", "MEDIUM"),
        ("profile.ts", "LOW"),
        ("navbar.tsx", "LOW"),
        ("tailwind.config.ts", "LOW"),
        ("README.md", "LOW"),
        ("package.json", "LOW"),
        ("eslint.config.js", "LOW"),
        ("auth-session.ts", "MEDIUM"),
        ("stripe-types.ts", "MEDIUM"),
        ("users-db.ts", "HIGH"),
        ("mailer.ts", "LOW"),
        ("i18n.ts", "LOW"),
        ("vite.config.ts", "LOW"),
        ("Dockerfile", "LOW"),
        ("webhook-retry.ts", "HIGH"),
        ("guest.ts", "HIGH"),
        ("footer.tsx", "LOW"),
    ]
    cases: list[GoldenCase] = []
    for i in range(1, 41):
        mock = {}
        for cid, tier in candidates:
            high = tier == "HIGH"
            mock[f"{cid}::relevant_to_task"] = 0.93 if high else 0.55 if tier == "MEDIUM" else 0.08
            mock[f"{cid}::useful_now"] = 0.91 if high else 0.50 if tier == "MEDIUM" else 0.06
            mock[f"{cid}::likely_noise"] = 0.05 if high else 0.35 if tier == "MEDIUM" else 0.90
        cases.append(
            GoldenCase(
                id=f"context-{i:04d}",
                category="rank_context",
                task="Fix Stripe guest webhook identity",
                input={
                    "task_goal": "Fix Stripe guest webhook identity",
                    "current_step": "inspect identity path",
                    "candidates": [
                        {"id": cid, "path": cid, "content": f"// {cid} {tier}"} for cid, tier in candidates
                    ],
                },
                labels=Labels(
                    expected_tiers={cid: tier for cid, tier in candidates},
                    critical_ids=[cid for cid, tier in candidates if tier == "HIGH"],
                    notes="critical Recall@10 must stay high; ranking only",
                ),
                mock_answers=mock,
            )
        )
    return cases


def classify_findings() -> list[GoldenCase]:
    cases: list[GoldenCase] = []
    for i in range(1, 51):
        cases.append(
            GoldenCase(
                id=f"finding-{i:04d}",
                category="classify_findings",
                task="Review checkout PR",
                input={
                    "task_goal": "Review checkout PR",
                    "requirements": [{"id": "R1", "text": "Resolve guest user"}],
                    "findings": [
                        {"id": "F1", "source": "lint", "text": "Missing trailing newline"},
                        {"id": "F2", "source": "human", "text": "Guest path never writes user id"},
                    ],
                },
                labels=Labels(
                    expected_band={"F2::requirement_related": "HIGH", "F1::requirement_related": "LOW"},
                    notes="style vs requirement-linked integrity",
                ),
                mock_answers={
                    "F1::likely_valid": 0.90,
                    "F1::requirement_related": 0.05,
                    "F1::requires_code_change": 0.70,
                    "F1::requires_replan": 0.04,
                    "F1::likely_duplicate": 0.10,
                    "F1::security_relevant": 0.02,
                    "F1::data_integrity_relevant": 0.02,
                    "F2::likely_valid": 0.88,
                    "F2::requirement_related": 0.93,
                    "F2::requires_code_change": 0.91,
                    "F2::requires_replan": 0.20,
                    "F2::likely_duplicate": 0.08,
                    "F2::security_relevant": 0.15,
                    "F2::data_integrity_relevant": 0.84,
                },
            )
        )
    return cases


def assess_risk() -> list[GoldenCase]:
    cases: list[GoldenCase] = []
    for i in range(1, 51):
        payment = i % 2 == 0
        cases.append(
            GoldenCase(
                id=f"risk-{i:04d}",
                category="assess_risk",
                task="Change checkout identity",
                input={
                    "task_goal": "Change checkout identity and Stripe webhook",
                    "changed_files": ["src/auth.ts", "src/webhooks/stripe.ts"],
                    "diff_summary": "trust client user id; capture earlier" if payment else "rename helper",
                },
                labels=Labels(
                    expected_band={
                        "authentication_sensitive": "HIGH" if payment else "UNCERTAIN",
                        "payment_sensitive": "HIGH" if payment else "LOW",
                    },
                    notes="triage only, not a security conclusion",
                ),
                mock_answers={
                    "security_sensitive": 0.91 if payment else 0.40,
                    "authentication_sensitive": 0.96 if payment else 0.45,
                    "authorization_sensitive": 0.80 if payment else 0.30,
                    "data_integrity_sensitive": 0.72 if payment else 0.20,
                    "schema_sensitive": 0.10,
                    "public_api_sensitive": 0.40,
                    "architecture_sensitive": 0.21,
                    "payment_sensitive": 0.84 if payment else 0.08,
                    "broad_regression_risk": 0.55,
                },
            )
        )
    return cases


def main() -> None:
    groups = {
        "compare_attempts": compare_attempts(),
        "triage_failure": triage_failure(),
        "check_completion": check_completion(),
        "rank_context": rank_context(),
        "classify_findings": classify_findings(),
        "assess_risk": assess_risk(),
    }
    total = 0
    for category, cases in groups.items():
        _write(category, cases)
        total += len(cases)
        print(f"{category}: {len(cases)}")
    print(f"total: {total}")


if __name__ == "__main__":
    main()
