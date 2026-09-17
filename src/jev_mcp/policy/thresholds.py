from __future__ import annotations

from jev_mcp.config import AppConfig
from jev_mcp.models import ProbabilityBands, StuckThresholds


class ThresholdSet:
    def __init__(self, config: AppConfig) -> None:
        self.bands: ProbabilityBands = config.thresholds.default
        self.stuck: StuckThresholds = config.thresholds.stuck
