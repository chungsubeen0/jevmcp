from __future__ import annotations

from typing import Literal

from jev_mcp.models import ProbabilityBands, StuckThresholds
from jev_mcp.policy.profiles import ProfilePolicy

Band = Literal["LOW", "UNCERTAIN", "HIGH"]
Relationship = Literal["LIKELY_RELATED", "UNCERTAIN", "LIKELY_UNRELATED"]
Scope = Literal["LIKELY_LOCAL", "UNCERTAIN", "LIKELY_BROAD"]
Escalation = Literal["NORMAL", "ELEVATED"]
StuckStatus = Literal["PROGRESSING", "UNCERTAIN", "LIKELY_STUCK"]
ControlSignal = Literal["CONTINUE", "REASSESS", "ESCALATE"]
CompletionStatus = Literal["APPEARS_COMPLETE", "REVIEW_REQUIRED", "INCOMPLETE"]
ContextTier = Literal["HIGH", "MEDIUM", "LOW"]


def band(probability: float, bands: ProbabilityBands) -> Band:
    if probability <= bands.low:
        return "LOW"
    if probability >= bands.high:
        return "HIGH"
    return "UNCERTAIN"


def triage_classification(
    signals: dict[str, float],
    bands: ProbabilityBands,
    profile: ProfilePolicy,
) -> dict[str, str]:
    related = signals.get("related_to_current_change", 0.5)
    localized = signals.get("likely_localized", 0.5)
    preexisting = signals.get("likely_preexisting", 0.5)
    deeper = signals.get("needs_deeper_reasoning", 0.5)

    if related >= bands.high:
        relationship: Relationship = "LIKELY_RELATED"
    elif related <= bands.low:
        relationship = "LIKELY_UNRELATED"
    else:
        relationship = "UNCERTAIN"

    if localized >= bands.high and preexisting <= bands.low:
        scope: Scope = "LIKELY_LOCAL"
    elif localized <= bands.low:
        scope = "LIKELY_BROAD"
    else:
        scope = "UNCERTAIN"

    elevate_at = 0.55 if profile.failure_triage == "aggressive" else bands.high
    escalation: Escalation = "ELEVATED" if deeper >= elevate_at else "NORMAL"
    return {
        "relationship": relationship,
        "scope": scope,
        "escalation": escalation,
    }


def stuck_decision(
    signals: dict[str, float],
    stuck: StuckThresholds,
    profile: ProfilePolicy,
) -> tuple[StuckStatus, ControlSignal]:
    same_failure = signals.get("same_failure", 0.0)
    same_strategy = signals.get("same_strategy", 0.0)
    new_evidence = signals.get("meaningful_new_evidence", 1.0)
    progress = signals.get("meaningful_progress", 1.0)
    reconsider = signals.get("reconsider_approach", 0.0)

    likely_stuck = (
        same_failure >= stuck.same_failure
        and same_strategy >= stuck.same_strategy
        and new_evidence <= stuck.max_new_evidence
        and progress <= stuck.max_progress
    )
    if likely_stuck:
        escalate_bar = 0.90 if profile.escalate_stuck_more_readily else 0.97
        if reconsider >= escalate_bar:
            return "LIKELY_STUCK", "ESCALATE"
        return "LIKELY_STUCK", "REASSESS"

    if progress >= 0.70 or (new_evidence >= 0.70 and same_strategy <= 0.40):
        return "PROGRESSING", "CONTINUE"

    return "UNCERTAIN", "CONTINUE"


def control_signal(status: StuckStatus, reconsider: float, profile: ProfilePolicy) -> ControlSignal:
    if status != "LIKELY_STUCK":
        return "CONTINUE"
    escalate_bar = 0.90 if profile.escalate_stuck_more_readily else 0.97
    return "ESCALATE" if reconsider >= escalate_bar else "REASSESS"


def completion_status(
    requirements: dict[str, dict[str, float]],
    signals: dict[str, float],
    bands: ProbabilityBands,
) -> tuple[CompletionStatus, list[str]]:
    review: list[str] = []
    unresolved = False
    for req_id, scores in requirements.items():
        satisfied = scores.get("appears_satisfied", 0.0)
        evidence = scores.get("evidence_present", 0.0)
        gap = scores.get("possible_gap", 0.0)
        if satisfied < bands.high or evidence < bands.high or gap > bands.low:
            review.append(req_id)
        if satisfied <= bands.low or gap >= bands.high:
            unresolved = True

    if signals.get("unresolved_requirement", 0.0) >= bands.high:
        unresolved = True
    if signals.get("further_review_warranted", 0.0) >= bands.high and not review:
        review = list(requirements)

    if unresolved:
        return "INCOMPLETE", review
    if review or signals.get("further_review_warranted", 0.0) >= bands.high:
        return "REVIEW_REQUIRED", review
    return "APPEARS_COMPLETE", []


def context_tier(
    relevant: float,
    useful_now: float,
    likely_noise: float,
    profile: ProfilePolicy,
) -> ContextTier:
    if useful_now >= profile.high_tier_useful_now and likely_noise <= profile.high_tier_max_noise:
        return "HIGH"
    if likely_noise >= 0.70 or (relevant <= 0.30 and useful_now <= 0.30):
        return "LOW"
    return "MEDIUM"


def attempt_user_decision(status: StuckStatus, signal: ControlSignal) -> str:
    """User-facing next-attempt advice. Never implements or changes the goal."""
    mapping: dict[tuple[StuckStatus, ControlSignal], str] = {
        ("PROGRESSING", "CONTINUE"): (
            "Stay on this approach. The next attempt should still aim at the predefined goal."
        ),
        ("UNCERTAIN", "CONTINUE"): (
            "Evidence is mixed. The user decides whether to stay or change approach. "
            "The predefined goal stays fixed."
        ),
        ("LIKELY_STUCK", "REASSESS"): (
            "Same strategy, little progress. The user should change the hypothesis "
            "before another similar attempt toward the goal."
        ),
        ("LIKELY_STUCK", "ESCALATE"): (
            "Repeating without progress. The user should stop this line of attempts "
            "and choose a different approach toward the goal."
        ),
    }
    return mapping.get(
        (status, signal),
        "The user decides the next attempt. The predefined goal is unchanged.",
    )


def completion_user_decision(status: CompletionStatus) -> str:
    if status == "INCOMPLETE":
        return (
            "Goal not reached. Keep implementing the listed requirements. "
            "The user decides the next attempt."
        )
    if status == "REVIEW_REQUIRED":
        return (
            "Possible gaps. The user reviews the listed requirements before treating "
            "the goal as done."
        )
    return (
        "Evidence looks complete. The user still decides whether the goal is achieved. "
        "Not a ship or merge decision."
    )


def triage_user_decision(classification: dict[str, str]) -> str:
    if classification.get("escalation") == "ELEVATED":
        return (
            "Deeper reasoning may help. The user decides whether to escalate investigation "
            "toward the predefined goal."
        )
    relationship = classification.get("relationship")
    if relationship == "LIKELY_RELATED":
        return (
            "Failure likely comes from this attempt. Stay on the current change toward "
            "the goal. Do not skip the failing check."
        )
    if relationship == "LIKELY_UNRELATED":
        return (
            "Failure may be off the goal path. The user decides scope. "
            "The failing check still stays in this attempt."
        )
    return (
        "Scope unclear. The user decides how to spend the next attempt. "
        "The predefined goal is unchanged."
    )


def rank_user_decision() -> str:
    return (
        "Inspect HIGH-tier candidates first for the next attempt toward the goal. "
        "Do not drop MEDIUM or LOW items."
    )


def findings_user_decision() -> str:
    return (
        "Use these likelihoods to decide which findings to act on in the next attempt. "
        "They do not confirm a defect."
    )


def risk_user_decision(review_warranted: bool) -> str:
    if review_warranted:
        return (
            "Change looks sensitive. The user decides whether to buy a deeper review "
            "before the next attempt. Not a security conclusion."
        )
    return (
        "No high-sensitivity signal. The user still decides the next attempt toward "
        "the goal. Not a safety certification."
    )


def risk_review_warranted(signals: dict[str, float], bands: ProbabilityBands) -> bool:
    sensitive_keys = (
        "security_sensitive",
        "authentication_sensitive",
        "authorization_sensitive",
        "data_integrity_sensitive",
        "payment_sensitive",
    )
    return any(signals.get(key, 0.0) >= bands.high for key in sensitive_keys)
