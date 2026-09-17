from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from jev_mcp.config import AppConfig, ProfileName

Aggressiveness = Literal["off", "optional", "conservative", "moderate", "enabled", "aggressive"]


@dataclass(frozen=True)
class ProfilePolicy:
    name: ProfileName
    failure_triage: Aggressiveness
    stuck_detection: Aggressiveness
    completion_check: bool
    context_ranking: Aggressiveness
    finding_classification: Aggressiveness
    risk_assessment: bool
    escalate_stuck_more_readily: bool
    high_tier_useful_now: float
    high_tier_max_noise: float


AUTONOMOUS = ProfilePolicy(
    name="autonomous",
    failure_triage="aggressive",
    stuck_detection="aggressive",
    completion_check=True,
    context_ranking="enabled",
    finding_classification="enabled",
    risk_assessment=True,
    escalate_stuck_more_readily=True,
    high_tier_useful_now=0.70,
    high_tier_max_noise=0.30,
)

INTERACTIVE = ProfilePolicy(
    name="interactive",
    failure_triage="moderate",
    stuck_detection="enabled",
    completion_check=True,
    context_ranking="conservative",
    finding_classification="optional",
    risk_assessment=True,
    escalate_stuck_more_readily=False,
    high_tier_useful_now=0.80,
    high_tier_max_noise=0.20,
)

CUSTOM = ProfilePolicy(
    name="custom",
    failure_triage="moderate",
    stuck_detection="enabled",
    completion_check=True,
    context_ranking="enabled",
    finding_classification="optional",
    risk_assessment=True,
    escalate_stuck_more_readily=False,
    high_tier_useful_now=0.70,
    high_tier_max_noise=0.30,
)

_PROFILES = {
    "autonomous": AUTONOMOUS,
    "interactive": INTERACTIVE,
    "custom": CUSTOM,
}


def resolve_profile(config: AppConfig, override: ProfileName | str | None = None) -> ProfilePolicy:
    name = override or config.profile.default
    return _PROFILES.get(str(name), INTERACTIVE)
