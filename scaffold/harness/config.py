"""
Tiered model configuration.

Tier by *capability needed per step*, not by habit:
  FRONTIER  - orchestration, planning, hard reasoning, final synthesis
  BALANCED  - routine sub-steps, most worker/sub-agent execution
  FAST      - classification, routing, extraction, guardrail checks

Model *names* belong in config (and age fast — verify before shipping). The
harness code only ever refers to tiers, so a model upgrade is a one-line change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ModelTier(Enum):
    FRONTIER = "frontier"
    BALANCED = "balanced"
    FAST = "fast"


@dataclass
class HarnessConfig:
    # tier -> model name (strings are provider-specific; set when you pick a provider)
    models: dict[ModelTier, str] = field(default_factory=lambda: {
        ModelTier.FRONTIER: "mock-frontier",
        ModelTier.BALANCED: "mock-balanced",
        ModelTier.FAST: "mock-fast",
    })
    # control-loop bounds
    max_iterations: int = 12
    token_budget: int = 100_000
    max_response_tokens: int = 4000
    temperature: float = 1.0
    # verification retries (how many times to feed feedback and let the agent fix)
    max_verify_retries: int = 2
    # safety
    require_approval_for_destructive: bool = True
    # context management
    compaction_threshold: float = 0.8
    keep_recent: int = 6
    # observability
    trace_path: Optional[str] = None
    # pricing for cost estimates (model -> (usd/1M in, usd/1M out)); ⚠ verify
    price_table: dict[str, tuple[float, float]] = field(default_factory=dict)

    def model_for(self, tier: ModelTier) -> str:
        # Robust to partial configs: prefer the requested tier, then BALANCED,
        # then any configured model. (Avoid dict.get's eager-default KeyError.)
        if tier in self.models:
            return self.models[tier]
        if ModelTier.BALANCED in self.models:
            return self.models[ModelTier.BALANCED]
        if self.models:
            return next(iter(self.models.values()))
        raise ValueError("HarnessConfig.models is empty; configure at least one tier")
